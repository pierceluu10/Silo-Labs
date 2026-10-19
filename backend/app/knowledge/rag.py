"""ChromaDB retrieval over MCU register specs and vendor docs.

Every register in every ``knowledge_data/<mcu>.svd`` becomes one document
(address, reset value, fields, descriptions); every ``## `` section of
``knowledge_data/vendor_docs/<mcu>.md`` becomes another; RP2040 errata are
indexed too. Agents call :func:`grounding_context` to pull the chunks most
relevant to their task, filtered to the target MCU.

Build the index once with ``python -m app.knowledge.rag``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chromadb

from app.config import get_settings

from .loader import KNOWLEDGE_DIR, PeripheralSpec, load_errata, load_svd_peripherals

log = logging.getLogger(__name__)

COLLECTION_NAME = "mcu_knowledge"
VENDOR_DOCS_DIR = KNOWLEDGE_DIR / "vendor_docs"
ERRATA_MCU = "rp2040"
DEFAULT_TOP_K = 8
DEFAULT_DOC_K = 3
MAX_FIELDS_PER_REGISTER = 16

KIND_REGISTER = "register"
KIND_VENDOR_DOC = "vendor_doc"
KIND_ERRATA = "errata"


class RagIndexMissingError(RuntimeError):
    """Raised when retrieval runs before the index has been built."""


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    distance: float


def indexed_mcus() -> list[str]:
    return sorted(p.stem for p in KNOWLEDGE_DIR.glob("*.svd"))


def _register_chunks(mcu: str, peripherals: dict[str, PeripheralSpec]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for pe in peripherals.values():
        for reg in pe.registers.values():
            fields = sorted(reg.fields.values(), key=lambda f: f.bit_offset, reverse=True)
            field_lines = [
                f"{f.name}[{f.bit_offset + f.bit_width - 1}:{f.bit_offset}] reset={f.reset_value}"
                + (f" - {f.description}" if f.description else "")
                for f in fields[:MAX_FIELDS_PER_REGISTER]
            ]
            text = (
                f"{mcu.upper()} register {pe.name}.{reg.name} at 0x{reg.address:08X} "
                f"(offset +0x{reg.offset:X}, {reg.size_bits}-bit, reset 0x{reg.reset_value:X}). "
                f"{reg.description}\nPeripheral {pe.name}: {pe.description}\nFields:\n"
                + "\n".join(field_lines)
            )
            chunks.append(
                Chunk(
                    id=f"{mcu}:reg:{pe.name}.{reg.name}",
                    text=text,
                    metadata={
                        "mcu": mcu,
                        "kind": KIND_REGISTER,
                        "source": f"{mcu}.svd {pe.name}.{reg.name}",
                    },
                )
            )
    return chunks


def _vendor_doc_chunks(path: Path) -> list[Chunk]:
    mcu = path.stem
    sections = re.split(r"^## ", path.read_text(), flags=re.MULTILINE)[1:]
    chunks: list[Chunk] = []
    for section in sections:
        title, _, body = section.partition("\n")
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        chunks.append(
            Chunk(
                id=f"{mcu}:doc:{slug}",
                text=f"{mcu.upper()} {title.strip()}\n{body.strip()}",
                metadata={"mcu": mcu, "kind": KIND_VENDOR_DOC, "source": f"vendor_docs/{path.name} § {title.strip()}"},
            )
        )
    return chunks


def _errata_chunks() -> list[Chunk]:
    return [
        Chunk(
            id=f"{ERRATA_MCU}:errata:{e['id']}",
            text=f"{ERRATA_MCU.upper()} erratum {e['id']}: " + " ".join(
                str(e[k]) for k in ("title", "description", "workaround") if e.get(k)
            ),
            metadata={"mcu": ERRATA_MCU, "kind": KIND_ERRATA, "source": f"errata.json {e['id']}"},
        )
        for e in load_errata()
    ]


def collect_chunks(mcus: list[str] | None = None) -> list[Chunk]:
    wanted = mcus or indexed_mcus()
    chunks: list[Chunk] = []
    for mcu in wanted:
        chunks.extend(_register_chunks(mcu, load_svd_peripherals(KNOWLEDGE_DIR / f"{mcu}.svd")))
        doc = VENDOR_DOCS_DIR / f"{mcu}.md"
        if doc.exists():
            chunks.extend(_vendor_doc_chunks(doc))
    if ERRATA_MCU in wanted:
        chunks.extend(_errata_chunks())
    return chunks


@lru_cache(maxsize=1)
def _client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(get_settings().chroma_path))


def build_index(mcus: list[str] | None = None) -> int:
    """(Re)build the collection from scratch. Returns the number of chunks indexed."""
    client = _client()
    if COLLECTION_NAME in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION_NAME)
    collection = client.create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    chunks = collect_chunks(mcus)
    batch = client.get_max_batch_size()
    for start in range(0, len(chunks), batch):
        part = chunks[start : start + batch]
        collection.add(
            ids=[c.id for c in part],
            documents=[c.text for c in part],
            metadatas=[c.metadata for c in part],
        )
        log.info("indexed %d/%d chunks", start + len(part), len(chunks))
    return len(chunks)


def retrieve(query: str, mcu: str, k: int = DEFAULT_TOP_K, kind: str | None = None) -> list[RetrievedChunk]:
    try:
        collection = _client().get_collection(COLLECTION_NAME)
    except chromadb.errors.NotFoundError as exc:
        raise RagIndexMissingError(
            "ChromaDB index not built. Run `python -m app.knowledge.rag` in backend/."
        ) from exc
    where = {"$and": [{"mcu": mcu}, {"kind": kind}]} if kind else {"mcu": mcu}
    result = collection.query(query_texts=[query], n_results=k, where=where)
    return [
        RetrievedChunk(Chunk(id=i, text=doc, metadata=meta), distance)
        for i, doc, meta, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        )
    ]


def grounding_context(query: str, mcu: str, k: int = DEFAULT_TOP_K, doc_k: int = DEFAULT_DOC_K) -> str:
    """Retrieved chunks rendered as a system-prompt section with source tags.

    Prose docs and registers are retrieved separately: thousands of register
    chunks would otherwise crowd the few vendor-doc sections out of the top k.
    """
    hits = [
        *retrieve(query, mcu, doc_k, kind=KIND_VENDOR_DOC),
        *retrieve(query, mcu, doc_k, kind=KIND_ERRATA),
        *retrieve(query, mcu, k, kind=KIND_REGISTER),
    ]
    lines = [f"# Retrieved {mcu.upper()} documentation (cite these; do not invent registers or pins)"]
    lines += [f"\n[{n}] {h.chunk.metadata['source']}\n{h.chunk.text}" for n, h in enumerate(hits, 1)]
    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    total = build_index()
    print(f"Indexed {total} chunks for {', '.join(indexed_mcus())} into {get_settings().chroma_path}")

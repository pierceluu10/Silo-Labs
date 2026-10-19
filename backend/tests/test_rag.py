"""RAG index tests against a real (temporary) ChromaDB built from the STM32F103 SVD + docs."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import get_settings
from app.knowledge import rag
from app.knowledge.rag import (
    KIND_REGISTER,
    KIND_VENDOR_DOC,
    RagIndexMissingError,
    build_index,
    collect_chunks,
    grounding_context,
    indexed_mcus,
    retrieve,
)


@pytest.fixture
def chroma_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setattr(get_settings(), "chroma_path", tmp_path)
    rag._client.cache_clear()
    yield tmp_path
    rag._client.cache_clear()


@pytest.fixture(scope="module")
def stm32_index(tmp_path_factory: pytest.TempPathFactory) -> Iterator[int]:
    settings = get_settings()
    original = settings.chroma_path
    settings.chroma_path = tmp_path_factory.mktemp("chroma")
    rag._client.cache_clear()
    count = build_index(["stm32f103"])
    yield count
    settings.chroma_path = original
    rag._client.cache_clear()


def test_chunks_cover_registers_docs_and_errata_for_every_mcu() -> None:
    chunks = collect_chunks()
    by_kind: dict[tuple[str, str], int] = {}
    for c in chunks:
        key = (c.metadata["mcu"], c.metadata["kind"])
        by_kind[key] = by_kind.get(key, 0) + 1
    print(f"chunk counts: {by_kind}")
    assert indexed_mcus() == ["esp32", "rp2040", "stm32f103"]
    for mcu in indexed_mcus():
        assert by_kind[(mcu, KIND_REGISTER)] > 500, mcu
        assert by_kind[(mcu, KIND_VENDOR_DOC)] >= 5, mcu
    assert by_kind[("rp2040", rag.KIND_ERRATA)] > 0
    assert sum(n for (_, kind), n in by_kind.items() if kind == KIND_REGISTER) > 1000
    assert len({c.id for c in chunks}) == len(chunks), "chunk ids must be unique for upsert"


def test_register_chunk_carries_authoritative_address() -> None:
    chunk = next(c for c in collect_chunks(["stm32f103"]) if c.id == "stm32f103:reg:I2C1.CCR")
    assert "0x4000541C" in chunk.text
    assert "F_S[15:15]" in chunk.text


def test_retrieve_before_build_raises(chroma_dir: Path) -> None:
    with pytest.raises(RagIndexMissingError):
        retrieve("I2C", "stm32f103")


def test_retrieval_finds_relevant_register(stm32_index: int) -> None:
    hits = retrieve("I2C fast mode clock control register CCR", "stm32f103", k=4, kind=KIND_REGISTER)
    sources = [h.chunk.metadata["source"] for h in hits]
    print(sources)
    assert any(s.endswith(("I2C1.CCR", "I2C2.CCR")) for s in sources)


def test_retrieval_finds_vendor_pin_mux_doc(stm32_index: int) -> None:
    hits = retrieve("which pins are I2C1 SDA and SCL", "stm32f103", k=1, kind=KIND_VENDOR_DOC)
    assert "PB7" in hits[0].chunk.text


def test_retrieval_is_filtered_to_target_mcu(stm32_index: int) -> None:
    assert retrieve("PLL_SYS feedback divider", "rp2040", k=3) == []
    assert all(h.chunk.metadata["mcu"] == "stm32f103" for h in retrieve("PLL", "stm32f103", k=5))


def test_grounding_context_cites_sources(stm32_index: int) -> None:
    context = grounding_context("USART1 baud rate 115200", "stm32f103")
    print(context[:800])
    assert context.startswith("# Retrieved STM32F103 documentation")
    assert "[1] vendor_docs/stm32f103.md" in context
    assert "stm32f103.svd USART" in context

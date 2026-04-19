"""Allow-listed HTTP fetcher with on-disk caching.

Trust boundary: agents must not be able to fetch arbitrary URLs (prompt
injection could otherwise force exfiltration to an attacker host). Every
request goes through :func:`fetch_doc`, which rejects hosts outside
``URL_ALLOWLIST`` and caches successful responses to
``~/.cache/silo-labs/research/<sha1>.txt``.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
from lxml import html as _html


URL_ALLOWLIST: tuple[str, ...] = (
    # Wokwi parts catalog + sim docs
    "docs.wokwi.com",
    # Raspberry Pi / RP2040 datasheet + SDK docs
    "www.raspberrypi.com",
    "datasheets.raspberrypi.com",
    "raspberrypi.github.io",
    # Adafruit learn guides (canonical hookup + datasheet copies)
    "learn.adafruit.com",
    "cdn-learn.adafruit.com",
    "cdn-shop.adafruit.com",
    # Vendor datasheet hosts
    "www.bosch-sensortec.com",
    "www.ti.com",
    "www.st.com",
    "www.nxp.com",
    "ww1.microchip.com",
    "www.analog.com",
    "developer.arm.com",
)


CACHE_DIR = Path.home() / ".cache" / "silo-labs" / "research"
DEFAULT_TIMEOUT_S = 10.0
DEFAULT_MAX_CHARS = 12_000


class ResearchError(RuntimeError):
    """Raised when a fetch is refused or fails."""


def _allowed(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(host == allowed or host.endswith("." + allowed) for allowed in URL_ALLOWLIST)


def _cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.txt"


def _strip_html(raw: str, max_chars: int) -> str:
    """Best-effort HTML -> readable text. Drops scripts, styles, nav blocks."""

    try:
        doc = _html.fromstring(raw)
    except Exception:
        # Fall back to a naive tag strip.
        text = re.sub(r"<[^>]+>", " ", raw)
        return re.sub(r"\s+", " ", text).strip()[:max_chars]

    # Drop boilerplate: scripts, styles, nav/footer chrome.
    for tag in ("script", "style", "nav", "footer", "header", "aside"):
        for el in list(doc.iter(tag)):
            try:
                el.drop_tree()
            except Exception:
                # Some lxml node kinds (Comments, etc.) lack drop_tree.
                pass
    text = doc.text_content() if hasattr(doc, "text_content") else _html.tostring(doc, method="text", encoding="unicode")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


async def fetch_html(url: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> str:
    if not _allowed(url):
        raise ResearchError(
            f"Refusing to fetch {url}: host not in URL_ALLOWLIST. "
            f"Allowed hosts: {', '.join(URL_ALLOWLIST)}"
        )
    async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "silo-labs-research/0.1"})
        resp.raise_for_status()
        return resp.text


async def fetch_doc(url: str, max_chars: int = DEFAULT_MAX_CHARS, force: bool = False) -> str:
    """Fetch ``url`` and return cleaned text (HTML stripped); cache the result.

    ``force=True`` bypasses the on-disk cache (useful if a doc changed).
    """

    cache = _cache_path(url)
    if not force and cache.exists():
        return cache.read_text()[:max_chars]
    raw = await fetch_html(url)
    text = _strip_html(raw, max_chars)
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text)
    except Exception:
        # Cache failures are non-fatal.
        pass
    return text
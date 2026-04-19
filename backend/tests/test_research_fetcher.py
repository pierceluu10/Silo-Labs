"""Research-fetcher tests. Allow-list rejection + cache + HTML scrub.

No live network: monkeypatches httpx so we never reach the internet.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.research import fetcher


def test_allowlist_rejects_unknown_host():
    assert not fetcher._allowed("https://evil.example.com/datasheet.pdf")
    assert not fetcher._allowed("not a url")


def test_allowlist_accepts_known_hosts():
    assert fetcher._allowed("https://docs.wokwi.com/parts/wokwi-mpu6050")
    assert fetcher._allowed("https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf")
    assert fetcher._allowed("https://learn.adafruit.com/foo")


def test_strip_html_removes_chrome():
    sample = (
        "<html><head><script>nope</script><style>.x{}</style></head>"
        "<body><nav>n</nav><h1>Hello</h1><p>World</p><footer>f</footer></body></html>"
    )
    out = fetcher._strip_html(sample, max_chars=200)
    assert "nope" not in out
    assert ".x{}" not in out
    assert "n" not in out.split()[:1]  # nav was dropped
    assert "Hello" in out
    assert "World" in out


@pytest.mark.asyncio
async def test_fetch_doc_refuses_unallowed_host():
    with pytest.raises(fetcher.ResearchError):
        await fetcher.fetch_html("https://evil.example.com/x")


@pytest.mark.asyncio
async def test_fetch_doc_uses_cache(monkeypatch, tmp_path):
    """If the cache file exists, fetch_doc reads it without calling httpx."""

    # Redirect cache dir to tmp_path.
    monkeypatch.setattr(fetcher, "CACHE_DIR", tmp_path)

    url = "https://docs.wokwi.com/parts/wokwi-mpu6050"
    cache_file = fetcher._cache_path(url)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("CACHED CONTENT")

    # If httpx ever gets called, error so we know cache wasn't used.
    async def boom(*_a, **_kw):
        raise AssertionError("should not have hit network")

    monkeypatch.setattr(fetcher, "fetch_html", boom)

    text = await fetcher.fetch_doc(url, max_chars=500)
    assert text == "CACHED CONTENT"
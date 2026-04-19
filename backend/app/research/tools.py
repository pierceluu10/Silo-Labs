"""LangChain ``@tool`` wrappers exposing the research fetcher to agents.

Agents bind the appropriate subset of these tools when constructing their LLM
chain (typically via ``llm.bind_tools([...])``). The supervisor / pinout /
wokwi / code agents each get the tools that match their job.
"""

from __future__ import annotations

from langchain_core.tools import tool

from .fetcher import URL_ALLOWLIST, ResearchError, fetch_doc


# Curated quick-lookup table for parts the supervisor/wokwi agent often needs
# but doesn't want to construct a URL for. Keys are lowercase device tokens
# (e.g. "bme280", "ssd1306", "mpu6050"). The mapping is intentionally small
# and biased toward Wokwi's part docs because that's where the embed cares.
_PART_DOC_INDEX: dict[str, str] = {
    "bme280": "https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout/python-circuitpython-test",
    "ssd1306": "https://docs.wokwi.com/parts/board-ssd1306",
    "mpu6050": "https://docs.wokwi.com/parts/wokwi-mpu6050",
    "ds18b20": "https://docs.wokwi.com/parts/wokwi-ds18b20",
    "lcd1602": "https://docs.wokwi.com/parts/wokwi-lcd1602",
    "hd44780": "https://docs.wokwi.com/parts/wokwi-lcd1602",
    "bmp180": "https://docs.wokwi.com/parts/board-bmp180",
    "neopixel": "https://docs.wokwi.com/parts/wokwi-neopixel-ring",
    "ws2812": "https://docs.wokwi.com/parts/wokwi-neopixel",
    "led": "https://docs.wokwi.com/parts/wokwi-led",
    "pushbutton": "https://docs.wokwi.com/parts/wokwi-pushbutton",
    "rp2040": "https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf",
    "pico": "https://docs.wokwi.com/parts/wokwi-pi-pico",
}


@tool
async def fetch_url(url: str) -> str:
    """Fetch a vendor documentation page (datasheet, SDK doc, Wokwi part).

    Only hosts on Silo Labs' allow-list are accepted — every other host is
    refused for safety. Returns cleaned plain text (max ~12k chars).
    """

    try:
        return await fetch_doc(url)
    except ResearchError as exc:
        return f"REFUSED: {exc}"
    except Exception as exc:  # pragma: no cover - depends on network
        return f"ERROR fetching {url}: {exc}"


@tool
async def fetch_part_doc(part_name: str) -> str:
    """Look up the canonical documentation page for a hardware part by name.

    Pass the device family (e.g. "BME280", "SSD1306", "MPU6050"). Returns
    cleaned page text. If no canonical URL is known the tool says so — agents
    should then either propose a fallback URL via ``fetch_url`` or note that
    documentation is unavailable.
    """

    key = part_name.strip().lower()
    url = _PART_DOC_INDEX.get(key)
    if url is None:
        return (
            f"NO_INDEX: no canonical documentation URL is registered for "
            f"part {part_name!r}. Allow-listed hosts: {', '.join(URL_ALLOWLIST)}."
        )
    try:
        return await fetch_doc(url)
    except ResearchError as exc:
        return f"REFUSED: {exc}"
    except Exception as exc:  # pragma: no cover
        return f"ERROR fetching {url}: {exc}"


def research_tools_for(agent: str) -> list:
    """Return the tools an agent should bind based on its role."""

    if agent in ("supervisor", "wokwi_diagram_generator"):
        return [fetch_part_doc, fetch_url]
    if agent in ("pinout_resolver", "code_composer"):
        return [fetch_part_doc, fetch_url]
    return []
"""Vendor-doc research subsystem.

Agents call the LangChain tools exposed in :mod:`app.research.tools` to fetch
real datasheet / wokwi-part / SDK-doc snippets from a strict allow-list of
hosts. Results are cached on disk so repeated lookups within (and across) runs
cost zero network round-trips.
"""

from .fetcher import URL_ALLOWLIST, fetch_doc, fetch_html  # noqa: F401
from .tools import (  # noqa: F401
    fetch_part_doc,
    fetch_url,
    research_tools_for,
)
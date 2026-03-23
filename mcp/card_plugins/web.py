"""Generic web fallback card data plugin.

Scrapes any URL using HTML parsing and OG meta extraction.
Used as a catch-all when no specialised plugin matches.
"""
from __future__ import annotations

from typing import Any

from . import CardDataPlugin
from ..card_text import _fetch_page_text


class WebCardPlugin(CardDataPlugin):
    """Generic HTML/OG-meta scraping fallback (priority 100)."""

    priority = 100

    @property
    def name(self) -> str:
        return "web"

    def can_handle(self, url: str, entity_type: str) -> bool:
        return True

    def fetch_page_data(self, url: str, entity_type: str) -> dict[str, Any] | None:
        if not url:
            return None
        return _fetch_page_text(url)

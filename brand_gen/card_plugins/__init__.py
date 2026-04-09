"""Card data plugin interface and registry.

Plugins are tried in ``priority`` order (lower = first).  The first
plugin whose ``can_handle`` returns *True* and whose ``fetch_page_data``
returns a non-``None`` dict wins.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CardDataPlugin(ABC):
    """Base class for card-data fetching plugins."""

    priority: int = 50  # lower = tried first

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def can_handle(self, url: str, entity_type: str) -> bool: ...

    @abstractmethod
    def fetch_page_data(self, url: str, entity_type: str) -> dict[str, Any] | None:
        """Return page dict: title, description, h1, h2, lines,
        optionally: share_card (dict), cid, source_kind."""
        ...


_PLUGINS: list[CardDataPlugin] = []


def register_plugin(plugin: CardDataPlugin) -> None:
    _PLUGINS.append(plugin)
    _PLUGINS.sort(key=lambda p: p.priority)


def clear_plugins() -> None:
    """Remove all registered plugins (for test isolation)."""
    _PLUGINS.clear()


def get_plugins() -> list[CardDataPlugin]:
    return list(_PLUGINS)


def fetch_card_page_data(url: str, entity_type: str) -> dict[str, Any] | None:
    """Try plugins in priority order. Return first non-None result."""
    for plugin in _PLUGINS:
        if plugin.can_handle(url, entity_type):
            result = plugin.fetch_page_data(url, entity_type)
            if result is not None:
                return result
    return None


# Auto-register built-in plugins at import time
from .sage import SageCardPlugin  # noqa: E402
from .web import WebCardPlugin  # noqa: E402

register_plugin(SageCardPlugin())   # priority 10
register_plugin(WebCardPlugin())    # priority 100

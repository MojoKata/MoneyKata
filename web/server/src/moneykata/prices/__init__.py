"""Price sources (requirements S4.2): integrations behind one interface, TickerSource. Each is
one module here that registers itself, so adding a source is adding a module."""

from . import coinbase, manual, massive, stub, tiingo  # noqa: F401 - each module registers its source
from .base import SOURCES, Quote, SourceError, TickerSource, register

__all__ = ["SOURCES", "Quote", "SourceError", "TickerSource", "register"]

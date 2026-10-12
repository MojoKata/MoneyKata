"""Every table, on one MetaData, one module per area (requirements §17.1.1)."""

from . import accounts, activity, core, prices, users  # noqa: F401 - each adds its tables
from ._base import metadata

__all__ = ["metadata"]

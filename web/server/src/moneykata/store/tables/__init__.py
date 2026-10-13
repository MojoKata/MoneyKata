"""Every table, on one MetaData, one module per area (requirements S14.1.1)."""

from . import accounts, activity, alerts, core, prices, sharing, users  # noqa: F401 - each adds its tables
from ._base import metadata

__all__ = ["metadata"]

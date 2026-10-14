"""Every table, on one MetaData, one module per area (requirements S14.1.1)."""

from . import (  # noqa: F401 - each adds its tables
    accounts,
    activity,
    alerts,
    assets,
    budgets,
    core,
    education,
    giving,
    loans,
    options,
    people,
    prices,
    projections,
    receipts,
    sharing,
    taxes,
    users,
)
from ._base import metadata

__all__ = ["metadata"]

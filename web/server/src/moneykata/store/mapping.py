"""Maps each entity onto its table (requirements §17.1.2). Imported once, at start."""

from sqlalchemy import event
from sqlalchemy.orm import registry

from .entities import Record, _now
from .entities import accounts as acc
from .entities import prices as pr
from .entities.core import Activity, Secret, Setting, TaskRun
from .entities.users import Group, OneTimeToken, Session, User, UserGroup
from .tables import accounts, activity, core, prices, users

mapper_registry = registry()
_done = False


def _versioned(entity, table, **kw) -> None:
    mapper_registry.map_imperatively(entity, table, version_id_col=table.c.version, **kw)


def map_all() -> None:
    global _done
    if _done:
        return
    _done = True
    _versioned(User, users.User)
    _versioned(Group, users.Group)
    mapper_registry.map_imperatively(UserGroup, users.UserGroups)
    mapper_registry.map_imperatively(Session, users.Session)
    mapper_registry.map_imperatively(OneTimeToken, users.OneTimeToken)
    for entity, table in (
        (acc.Category, accounts.Category),
        (acc.Account, accounts.Account),
        (acc.Instrument, accounts.Instrument),
        (acc.ImportMapping, accounts.ImportMapping),
        (acc.Import, accounts.Import),
        (acc.Transaction, accounts.Transaction),
        (acc.Split, accounts.Split),
        (acc.Lot, accounts.Lot),
        (acc.Holding, accounts.Holding),
        (acc.Anchor, accounts.Anchor),
        (acc.Reconciliation, accounts.Reconciliation),
    ):
        _versioned(entity, table)
    mapper_registry.map_imperatively(acc.TransactionTag, accounts.TransactionTags)
    mapper_registry.map_imperatively(acc.LotPick, accounts.LotPicks)
    _versioned(pr.PriceSource, prices.PriceSource)
    _versioned(pr.Price, prices.Price)
    _versioned(Setting, core.Setting)
    mapper_registry.map_imperatively(Secret, core.Secret)
    mapper_registry.map_imperatively(TaskRun, core.TaskRun)
    mapper_registry.map_imperatively(Activity, activity.Activity)


@event.listens_for(Record, "before_update", propagate=True)
def _touch(mapper, connection, target) -> None:
    target.updatedAt = _now()


@event.listens_for(Setting, "before_update")
def _touch_setting(mapper, connection, target) -> None:
    target.updatedAt = _now()

"""Maps each entity onto its table (requirements §17.1.2). Imported once, at start."""

from sqlalchemy import event
from sqlalchemy.orm import registry

from .entities import Record, _now
from .entities.core import Activity, Secret, Setting, TaskRun
from .entities.users import Group, OneTimeToken, Session, User, UserGroup
from .tables import activity, core, users

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

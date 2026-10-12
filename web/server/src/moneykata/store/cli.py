"""`moneykata db …` (requirements §17.7)."""

from pathlib import Path

from ..config import load


def register(sub) -> None:
    d = sub.add_parser("db", help="the database")
    ds = d.add_subparsers(dest="db_command", required=True)
    ds.add_parser(
        "shell", help="SQL against the encrypted database (as root on the host)"
    ).set_defaults(func=_shell)
    ds.add_parser("backup", help="make a verified backup now").set_defaults(func=_backup)


def _shell(args) -> int:
    from .maintenance import shell

    return shell(load(Path(args.config)))


def _backup(args) -> int:
    from .. import settings
    from .maintenance import backup, open_store, prune

    config = load(Path(args.config))
    store = open_store(config)
    path = backup(config, store)
    with store.db.read() as s:
        keep = settings.get(s, "backupCopies")
    prune(config, keep)
    print(path)
    return 0

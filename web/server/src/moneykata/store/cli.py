"""`moneykata db …` (requirements S14.7): each asks for the recovery phrase, the only key
there is (S15.4)."""

from pathlib import Path

from ..config import load
from ..keys.cli import read_phrase


def register(sub) -> None:
    d = sub.add_parser("db", help="the database")
    ds = d.add_subparsers(dest="db_command", required=True)
    ds.add_parser("shell", help="SQL against the encrypted database (on the host)").set_defaults(
        func=_shell
    )
    ds.add_parser("backup", help="make a verified backup now").set_defaults(func=_backup)
    v = ds.add_parser(
        "verify-backup",
        help="check a backup is whole and opens with the phrase (the newest by default)",
    )
    v.add_argument("path", nargs="?", help="a backup folder")
    v.set_defaults(func=_verify_backup)
    r = ds.add_parser("restore", help="restore a backup, with the server stopped")
    r.add_argument("path", help="the backup folder to restore")
    r.set_defaults(func=_restore)


def _shell(args) -> int:
    from .maintenance import queue_host_event, shell

    config = load(Path(args.config))
    queue_host_event(config, "db.shell", {})
    return shell(config, read_phrase())


def _backup(args) -> int:
    """Through the running server when it is up, over its socket (S15.4.7); with the phrase
    typed when it is stopped."""
    from .. import host, settings
    from ..config import RefuseStart
    from .maintenance import backup, open_store, prune, queue_host_event

    config = load(Path(args.config))
    try:
        with host.client(config, timeout=600) as c:
            r = c.post("/host/backup")
    except host.NotRunning:
        r = None
    if r is not None:
        if r.status_code != 200:
            raise RefuseStart(f"the server refused the backup: {host.detail(r)}")
        print(r.json()["path"])
        return 0
    store = open_store(config, read_phrase())
    path = backup(config, store)
    with store.db.read() as s:
        keep = settings.get(s, "backupCopies")
    prune(config, keep)
    queue_host_event(config, "db.backup", {"name": path.name})
    print(path)
    return 0


def _verify_backup(args) -> int:
    from .maintenance import queue_host_event, verify_backup

    config = load(Path(args.config))
    path = verify_backup(config, read_phrase(), Path(args.path) if args.path else None)
    queue_host_event(config, "db.verify-backup", {"name": path.name})
    print(f"{path.name}: whole, and opens with that phrase")
    return 0


def _restore(args) -> int:
    from .maintenance import queue_host_event, restore

    config = load(Path(args.config))
    aside = restore(config, Path(args.path), read_phrase())
    queue_host_event(config, "db.restore", {"name": Path(args.path).name, "aside": aside.name})
    print(f"restored {Path(args.path).name}; what it replaced is in {aside}")
    print("start the server and unlock it: it opens the restored database, migrating it if needed")
    return 0

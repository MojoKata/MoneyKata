"""`moneykata db …` (requirements S14.7)."""

from pathlib import Path

from ..config import load


def register(sub) -> None:
    d = sub.add_parser("db", help="the database")
    ds = d.add_subparsers(dest="db_command", required=True)
    ds.add_parser(
        "shell", help="SQL against the encrypted database (as root on the host)"
    ).set_defaults(func=_shell)
    ds.add_parser("backup", help="make a verified backup now").set_defaults(func=_backup)
    v = ds.add_parser(
        "verify-backup",
        help="check a backup is whole and opens with the key (the newest by default)",
    )
    v.add_argument("path", nargs="?", help="a backup folder")
    v.set_defaults(func=_verify_backup)
    r = ds.add_parser("restore", help="restore a backup, with the server stopped")
    r.add_argument("path", help="the backup folder to restore")
    r.set_defaults(func=_restore)


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


def _verify_backup(args) -> int:
    from .maintenance import verify_backup

    path = verify_backup(load(Path(args.config)), Path(args.path) if args.path else None)
    print(f"{path.name}: whole, and opens with the master key")
    return 0


def _restore(args) -> int:
    from .maintenance import restore

    aside = restore(load(Path(args.config)), Path(args.path))
    print(f"restored {Path(args.path).name}; what it replaced is in {aside}")
    print("start the server: it opens the restored database and migrates it if needed")
    return 0

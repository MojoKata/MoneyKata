"""`moneykata keys …` (requirements §18.4.6, §18.6, §18.7): run on the host, as one-off
containers of the same image. Only `init` and `rotate` need the key directory writable."""

import datetime as dt
import os
import re
import secrets as pysecrets
from collections.abc import Callable
from pathlib import Path

from ..config import Config, PreviousKey, RefuseStart, load
from . import master, phrase

SERVER_UID = 10001

Ask = Callable[[str], str]
Say = Callable[[str], None]


def _say(text: str) -> None:
    print(text)


def sheet(master_key: bytes, server: str, when: dt.date) -> str:
    """The recovery sheet: 12 numbered words with the fingerprint, server and date."""
    words = phrase.to_words(master_key)
    rows = [f"  {i:>2}. {w}" for i, w in enumerate(words, 1)]
    return "\n".join(
        [
            "MoneyKata master key recovery phrase",
            "",
            f"  server:       {server}",
            f"  fingerprint:  {master.fingerprint(master_key)}",
            f"  made:         {when.isoformat()}",
            "",
            *rows,
            "",
            "Keep at least two copies in two places, one of them offline, and never with the",
            "backups. Losing both the key file and these words loses everything this server holds.",
        ]
    )


def matches(word: str, typed: str) -> bool:
    """A word typed in full, or by its first four letters (which identify it)."""
    return typed == word or (len(typed) >= 4 and word.startswith(typed))


def confirm_three(master_key: bytes, ask: Ask, say: Say, tries: int = 3) -> bool:
    """Ask for three words chosen at random; the key is saved only when they are right."""
    words = phrase.to_words(master_key)
    for _ in range(tries):
        picks = sorted(pysecrets.SystemRandom().sample(range(12), 3))
        ok = True
        for i in picks:
            answer = ask(f"word {i + 1}: ").strip().lower()
            if not matches(words[i], answer):
                ok = False
        if ok:
            return True
        say("That is not right. Check the sheet and try again.")
    return False


def _owner() -> int | None:
    """Run as root (the one-off container), the files go to the server's account."""
    return SERVER_UID if os.geteuid() == 0 else None


def init(
    config: Config,
    ask: Ask = input,
    say: Say = _say,
    from_phrase: bool = False,
    confirm: bool = True,
) -> bytes:
    if config.key_file.exists():
        raise RefuseStart(f"{config.key_file} already exists; `keys init` never overwrites a key")
    config.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    ring_exists = config.keyring_path.exists()
    if from_phrase:
        try:
            master_key = phrase.from_words(ask("recovery phrase (12 words): "))
        except phrase.PhraseError as e:
            raise RefuseStart(str(e)) from None
        if ring_exists:
            ring = master.read_keyring(config.keyring_path)
            if master.key_id(master_key) != ring.master_id:
                raise RefuseStart(
                    f"these words are key {master.fingerprint(master_key)}, but the data "
                    f"directory's keyring was wrapped by {master.fingerprint(ring.master_id)}"
                )
            master.unwrap(master_key, ring)
            say(f"The words match the keyring ({master.fingerprint(master_key)}).")
        else:
            now = master.now()
            ring = master.wrap(master_key, master.new_data_key(), now, now)
            master.write_keyring(config.keyring_path, ring, _owner())
    else:
        if ring_exists:
            raise RefuseStart(
                f"{config.keyring_path} already exists: this data directory "
                "has a key. Use `keys init --from-phrase` to write it back."
            )
        master_key = master.new_master()
        say(sheet(master_key, config.name, dt.date.today()))
        if confirm:
            say("\nType back three of the words to show they are written down.")
            if not confirm_three(master_key, ask, say):
                raise RefuseStart("the words were not confirmed; no key was saved")
        now = master.now()
        ring = master.wrap(master_key, master.new_data_key(), now, now)
        master.write_keyring(config.keyring_path, ring, _owner())
    master.write_key_file(config.key_file, master_key, _owner())
    say(f"Saved {config.key_file} ({master.fingerprint(master_key)}).")
    return master_key


def check(config: Config, say: Say = _say) -> master.Unlocked:
    unlocked = master.open_keys(config)
    say(f"ok: {master.fingerprint(unlocked.master_id)} unwraps the data key")
    return unlocked


def _read(config: Config) -> bytes:
    return master.check_key_file(config.key_file, config.data_dir, config.backup_dir)


def show_phrase(config: Config, say: Say = _say, file: Path | None = None) -> None:
    key = _read(config)
    ring = master.read_keyring(config.keyring_path)
    text = sheet(key, config.name, ring.master_created.date())
    if file:
        fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(text + "\n")
        say(f"Wrote the recovery sheet to {file}. Print it, then delete the file.")
    else:
        say(text)


def verify(
    config: Config,
    ask: Ask = input,
    say: Say = _say,
    record: Callable[[str, bool], None] | None = None,
) -> bool:
    """Whether a typed phrase matches the running key, changing nothing (§18.6.5)."""
    key = _read(config)
    try:
        typed = phrase.from_words(ask("recovery phrase (12 words): "))
    except phrase.PhraseError as e:
        say(f"not a valid phrase: {e}")
        return False
    ok = pysecrets.compare_digest(typed, key)
    say(
        f"match: the phrase is the key {master.fingerprint(key)}"
        if ok
        else "no match: these words are a different key"
    )
    if record:
        record(master.key_id(key), ok)
    return ok


def rotate(config: Config, ask: Ask = input, say: Say = _say) -> tuple[str, str]:
    """A new master key re-wraps the data key in one step (§18.7.1). Nothing else changes."""
    if config.path is None:
        raise RefuseStart(
            "rotation records the previous key in moneykata.toml: run it with --config"
        )
    # Everything rotation writes is checked first, so a read-only mount stops it before any
    # key is moved rather than halfway through.
    for target in (config.path, config.key_file.parent, config.keyring_path.parent):
        if not os.access(target, os.W_OK):
            raise RefuseStart(
                f"{target} is not writable: rotation writes the key directory, the keyring and "
                "moneykata.toml (in Docker: `docker compose run --rm keys-rotate`)"
            )
    old_key = _read(config)
    ring = master.read_keyring(config.keyring_path)
    data_key = master.unwrap(old_key, ring)
    new_key = master.new_master()
    say(sheet(new_key, config.name, dt.date.today()))
    say("\nType back three of the words to show they are written down.")
    if not confirm_three(new_key, ask, say):
        raise RefuseStart("the words were not confirmed; the key was not rotated")
    stamp = dt.date.today().strftime("%Y%m%d")
    kept = config.key_file.with_name(f"{config.key_file.stem}-{stamp}{config.key_file.suffix}")
    n = 1
    while kept.exists():
        n += 1
        kept = kept.with_name(f"{config.key_file.stem}-{stamp}-{n}{config.key_file.suffix}")
    os.rename(config.key_file, kept)
    master.write_key_file(config.key_file, new_key, _owner())
    new_ring = master.wrap(new_key, data_key, master.now(), ring.data_key_created)
    master.write_keyring(config.keyring_path, new_ring, _owner())
    previous = (*config.previous_keys, PreviousKey(kept, master.fingerprint(old_key)))
    write_previous(config.path, previous)
    old_fp, new_fp = master.fingerprint(old_key), master.fingerprint(new_key)
    say(f"Rotated: {old_fp} → {new_fp}. Back up the new phrase now, then restart the server.")
    say(f"Keep {kept.name} until every backup made before today has been pruned.")
    return old_fp, new_fp


def write_previous(path: Path, previous: tuple[PreviousKey, ...]) -> None:
    """Set `previous = [...]` under [keys] in moneykata.toml, keeping the rest as written."""
    text = path.read_text()
    entries = ", ".join(
        f'{{ path = "{p.path}", fingerprint = "{p.fingerprint}" }}' for p in previous
    )
    line = f"previous = [{entries}]"
    lines = text.splitlines()
    start = next((i for i, x in enumerate(lines) if x.strip() == "[keys]"), None)
    if start is None:
        lines += ["", "[keys]", line]
    else:
        end = next(
            (i for i in range(start + 1, len(lines)) if re.match(r"^\s*\[", lines[i])), len(lines)
        )
        for i in range(start + 1, end):
            if re.match(r"^\s*previous\s*=", lines[i]):
                lines[i] = line
                break
        else:
            lines.insert(end, line)
    with open(path, "r+") as f:  # in place: the file may be a single-file bind mount
        f.seek(0)
        f.write("\n".join(lines) + "\n")
        f.truncate()


def register(sub) -> None:
    k = sub.add_parser("keys", help="the master key and its recovery phrase (§18)")
    ks = k.add_subparsers(dest="keys_command", required=True)
    i = ks.add_parser("init", help="make the master key and the data key")
    i.add_argument(
        "--from-phrase", action="store_true", help="write the key back from its recovery phrase"
    )
    i.set_defaults(func=lambda a: (init(load(Path(a.config)), from_phrase=a.from_phrase), 0)[1])
    ks.add_parser("check", help="run the start-up checks on the key").set_defaults(
        func=lambda a: (check(load(Path(a.config))), 0)[1]
    )
    ks.add_parser("fingerprint", help="print the key's fingerprint").set_defaults(
        func=lambda a: (print(master.fingerprint(_read(load(Path(a.config))))), 0)[1]
    )
    p = ks.add_parser("phrase", help="show the recovery phrase again")
    p.add_argument("--file", type=Path, help="write it as a recovery sheet to print")
    p.set_defaults(func=lambda a: (show_phrase(load(Path(a.config)), file=a.file), 0)[1])
    ks.add_parser("verify", help="check a typed phrase against the key").set_defaults(
        func=_verify_cmd
    )
    ks.add_parser("rotate", help="replace the master key").set_defaults(func=_rotate_cmd)


def _verify_cmd(args) -> int:
    from ..store.maintenance import record_key_event

    config = load(Path(args.config))
    ok = verify(
        config,
        record=lambda kid, ok: record_key_event(
            config,
            "key.verified" if ok else "key.verify-failed",
            {"fingerprint": master.fingerprint(kid)},
        ),
    )
    return 0 if ok else 1


def _rotate_cmd(args) -> int:
    from ..store.maintenance import record_key_event

    config = load(Path(args.config))
    old_fp, new_fp = rotate(config)
    record_key_event(load(Path(args.config)), "key.rotated", {"from": old_fp, "to": new_fp})
    return 0

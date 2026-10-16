"""`moneykata keys …` (requirements S15.4, S15.6, S15.7): run on the host as one-off
containers of the same image, or, for `unlock` and `rotate`, against the server running on
this host, over its Unix socket (host.py). The
master key is the recovery phrase: every command that needs it asks for it, and none writes
it anywhere. What a command did is queued for Activity (`maintenance.queue_host_event`), since
a one-off container cannot open the database without the phrase."""

import datetime as dt
import getpass
import os
import secrets as pysecrets
from collections.abc import Callable
from pathlib import Path

from ..config import Config, RefuseStart, load
from . import master, phrase

SERVER_UID = 10001

Ask = Callable[[str], str]
Say = Callable[[str], None]


def _say(text: str) -> None:
    print(text)


def _hidden(prompt: str) -> str:
    return getpass.getpass(prompt)


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
            "These words are the master key, and they are never stored: the server asks for",
            "them at every start. Keep at least two copies in two places, one of them offline.",
            "Losing them loses everything this server holds, and every backup of it.",
        ]
    )


def matches(word: str, typed: str) -> bool:
    """A word typed in full, or by its first four letters (which identify it)."""
    return typed == word or (len(typed) >= 4 and word.startswith(typed))


def confirm_three(master_key: bytes, ask: Ask, say: Say, tries: int = 3) -> bool:
    """Ask for three words chosen at random; the key counts as written down only when they
    are right."""
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


def read_phrase(ask: Ask = _hidden, prompt: str = "recovery phrase (12 words): ") -> bytes:
    """The master key from a typed phrase; a phrase that isn't one refuses the command."""
    try:
        return phrase.from_words(ask(prompt))
    except phrase.PhraseError as e:
        raise RefuseStart(f"not a valid phrase: {e}") from None


def init(
    config: Config,
    ask: Ask = input,
    say: Say = _say,
    confirm: bool = True,
    master_key: bytes | None = None,
) -> bytes:
    """A fresh data directory's keys: a new master key, shown as its phrase and confirmed by
    three words typed back, and a new data key wrapped under it in the keyring. Nothing of the
    master key is written (S15.4.2)."""
    if config.keyring_path.exists():
        raise RefuseStart(
            f"{config.keyring_path} already exists: this data directory has a key. A backup "
            "brings its own keyring back with `db restore`; `keys init` is for a new server."
        )
    config.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    master_key = master_key or master.new_master()
    say(sheet(master_key, config.name, dt.date.today()))
    if confirm:
        say("\nType back three of the words to show they are written down.")
        if not confirm_three(master_key, ask, say):
            raise RefuseStart("the words were not confirmed; no key was made")
    now = master.now()
    ring = master.wrap(master_key, master.new_data_key(), now, now)
    master.write_keyring(config.keyring_path, ring, _owner())
    say(
        f"Made the keyring for {master.fingerprint(master_key)}. The phrase is the key and is "
        "not stored: start the server, then unlock it with the phrase."
    )
    return master_key


def fingerprint_of(config: Config) -> str:
    """The fingerprint of the master key the keyring was wrapped under; no phrase needed."""
    return master.fingerprint(master.read_keyring(config.keyring_path).master_id)


def verify(
    config: Config,
    ask: Ask = _hidden,
    say: Say = _say,
    record: Callable[[str, bool], None] | None = None,
) -> bool:
    """Whether a typed phrase unwraps this server's keyring, changing nothing (S15.6.5)."""
    ring = master.read_keyring(config.keyring_path)
    try:
        typed = phrase.from_words(ask("recovery phrase (12 words): "))
    except phrase.PhraseError as e:
        say(f"not a valid phrase: {e}")
        return False
    try:
        master.unwrap(typed, ring)
        ok = True
    except ValueError:
        ok = False
    say(
        f"match: the phrase is the key {master.fingerprint(ring.master_id)}"
        if ok
        else f"no match: these words are {master.fingerprint(typed)}, not this server's key "
        f"{master.fingerprint(ring.master_id)}"
    )
    if record:
        record(ring.master_id, ok)
    return ok


def pending_reencrypt(config: Config) -> Path:
    return config.keyring_path.with_name(config.keyring_path.name + ".next")


def _running(config: Config) -> bool:
    """Whether the server is up on this host and unlocked, asked over its socket (S13.6). One
    that is up and locked refuses the command: unlock it, or stop it to work offline."""
    from .. import host

    try:
        with host.client(config, timeout=5) as c:
            r = c.get("/host/unlock")
    except host.NotRunning:
        return False
    if r.status_code == 200 and r.json().get("locked"):
        raise RefuseStart(
            "the server is running and locked: unlock it first (`keys unlock`), or stop it"
        )
    return r.status_code == 200


CHOICES = {"r": "rewrap", "d": "delete", "l": "leave", "": "rewrap"}


def ask_copies(found: list[dict], ask: Ask, say: Say, all_: str | None = None) -> dict[str, str]:
    """Each copy's choice (S15.7.1): re-wrap (the default), delete or leave; `all_` answers
    for every copy (`--rewrap-all`, `--delete-old`, `--leave-all`)."""
    if not found:
        return {}
    out = {}
    say(f"\n{len(found)} copies on this host (the host's own snapshots and backups are not here):")
    for c in found:
        how = {
            "current": "re-wraps with the key the server holds",
            "phrase": "re-wraps with the current phrase",
            "previous": f"needs the phrase of {c.get('masterKey')}",
            "unknown": "its keyring cannot be read",
        }[c["opens"]]
        line = f"  {c['name']} ({c['kind']}, {c['made'][:10]}, {c['bytes'] // 1048576} MB): {how}"
        if all_ is not None:
            out[c["name"]] = all_
            continue
        say(line)
        answer = ask("    [R]e-wrap, [d]elete or [l]eave (R): ").strip().lower()[:1]
        out[c["name"]] = CHOICES.get(answer, "rewrap")
    return out


def rotate(
    config: Config,
    ask: Ask = input,
    say: Say = _say,
    ask_hidden: Ask = _hidden,
    running: bool | None = None,
    all_copies: str | None = None,
) -> tuple[str, str]:
    """A new master key re-wraps the data key in one step (S15.7.1): the new phrase shown and
    confirmed, the keyring written with the old key recorded, and each copy on the host
    re-wrapped, deleted or left. Through the running server when it is up (it holds the data
    key, so no old phrase is needed: the way out of a lost phrase); with the old phrase typed
    when it is stopped."""
    running = _running(config) if running is None else running
    if running:
        return _rotate_online(config, ask, say, ask_hidden, all_copies)
    from ..store import copies as copies_

    if not os.access(config.keyring_path.parent, os.W_OK):
        raise RefuseStart(
            f"{config.keyring_path.parent} is not writable: rotation writes the keyring "
            "(in Docker: `docker compose run --rm moneykata keys rotate`)"
        )
    if pending_reencrypt(config).exists():
        raise RefuseStart(
            "a re-encryption is pending: start and unlock the server so it finishes, then rotate"
        )
    old_key = read_phrase(ask_hidden, "current recovery phrase (12 words): ")
    ring = master.read_keyring(config.keyring_path)
    try:
        data_key = master.unwrap(old_key, ring)
    except ValueError:
        raise RefuseStart(
            f"those words are {master.fingerprint(old_key)}, not this server's key "
            f"{master.fingerprint(ring.master_id)}"
        ) from None
    current = master.Unlocked(ring.master_id, ring, master.DataKeys.derive(data_key), data_key)
    found = copies_.copies(config)
    choices = ask_copies(
        [
            {
                "name": c.name,
                "kind": c.kind,
                "made": c.made.isoformat(),
                "bytes": c.bytes,
                "masterKey": master.fingerprint(c.ring.master_id) if c.ring else None,
                "opens": copies_.opens_with(c, current),
            }
            for c in found
        ],
        ask,
        say,
        all_copies,
    )
    new_key = master.new_master()
    say(sheet(new_key, config.name, dt.date.today()))
    say("\nType back three of the words to show they are written down.")
    if not confirm_three(new_key, ask, say):
        raise RefuseStart("the words were not confirmed; the key was not rotated")
    at = master.now()
    master.write_keyring(config.keyring_path, master.rotated(ring, data_key, new_key, at), _owner())
    outcomes = copies_.apply_rotation(config, choices, current, new_key, at, old_key)
    old_fp, new_fp = master.fingerprint(old_key), master.fingerprint(new_key)
    _said_rotated(say, old_fp, new_fp, outcomes)
    return old_fp, new_fp


def _rotate_online(
    config: Config, ask: Ask, say: Say, ask_hidden: Ask, all_copies: str | None
) -> tuple[str, str]:
    from .. import host

    with host.client(config, timeout=600) as c:
        r = c.get("/host/keys/copies")
        if r.status_code != 200:
            raise RefuseStart(f"the server refused: {host.detail(r)}")
        found = r.json()["copies"]
        choices = ask_copies(found, ask, say, all_copies)
        old_words = None
        needs_old = [
            c for c in found if choices.get(c["name"]) == "rewrap" and c["opens"] != "current"
        ]
        if needs_old:
            say(
                f"\n{len(needs_old)} of those hold an earlier data key: re-wrapping them needs "
                "the current phrase. Type it, or press Enter to leave them as they are."
            )
            old_words = ask_hidden("current recovery phrase (Enter to skip): ").strip() or None
            if old_words:
                try:
                    phrase.from_words(old_words)
                except phrase.PhraseError as e:
                    raise RefuseStart(f"not a valid phrase: {e}") from None
        new_key = master.new_master()
        say(sheet(new_key, config.name, dt.date.today()))
        say("\nType back three of the words to show they are written down.")
        if not confirm_three(new_key, ask, say):
            raise RefuseStart("the words were not confirmed; the key was not rotated")
        r = c.post(
            "/host/keys/rotate",
            json={
                "phrase": " ".join(phrase.to_words(new_key)),
                "oldPhrase": old_words,
                "copies": choices,
            },
        )
    if r.status_code != 200:
        raise RefuseStart(f"the server refused the rotation: {host.detail(r)}")
    out = r.json()
    _said_rotated(say, out["from"], out["to"], out.get("copies") or {})
    return out["from"], out["to"]


def _said_rotated(say: Say, old_fp: str, new_fp: str, outcomes: dict[str, str]) -> None:
    say(f"Rotated: {old_fp} → {new_fp}. Back up the new phrase now.")
    for name, outcome in outcomes.items():
        say(f"  {name}: {outcome}")
    left = [n for n, o in outcomes.items() if o.startswith("left")]
    say(
        "The server unlocks with the new phrase from its next start. "
        + (
            f"Keep the old phrase: {len(left)} copies here still need it, and so do the host's "
            "snapshots and backups made before today (S15.7.1)."
            if left
            else "Nothing here needs the old phrase; the host's snapshots and backups made "
            "before today still do, for as long as they are kept (S15.7.1)."
        )
    )


def unlock(config: Config, ask: Ask = _hidden, say: Say = _say) -> int:
    """`moneykata keys unlock` (S15.4.2): the phrase handed to the server running on this
    host over its Unix socket, never the network, to the same unlock as the locked screen's."""
    from .. import host

    words = ask("recovery phrase (12 words): ")
    try:
        phrase.from_words(words)
    except phrase.PhraseError as e:
        say(f"refused: not a valid phrase: {e}")
        return 1
    try:
        with host.client(config, timeout=300) as c:
            r = c.post("/host/unlock", json={"phrase": words})
    except host.NotRunning as e:
        say(f"refused: {e}")
        return 1
    if r.status_code == 200:
        say(f"unlocked: {r.json().get('fingerprint', '')}")
        return 0
    say(f"refused: {host.detail(r)}")
    return 1


def register(sub) -> None:
    k = sub.add_parser("keys", help="the master key: its recovery phrase and the keyring (S15)")
    ks = k.add_subparsers(dest="keys_command", required=True)
    ks.add_parser(
        "init", help="a new master key, shown as its phrase, and a new data key"
    ).set_defaults(func=lambda a: (init(load(Path(a.config))), 0)[1])
    ks.add_parser("fingerprint", help="print the fingerprint of the key in use").set_defaults(
        func=lambda a: (print(fingerprint_of(load(Path(a.config)))), 0)[1]
    )
    ks.add_parser("verify", help="check a typed phrase against the keyring").set_defaults(
        func=_verify_cmd
    )
    r = ks.add_parser(
        "rotate", help="a new master key and phrase: through the running server, or offline"
    )
    g = r.add_mutually_exclusive_group()
    g.add_argument("--rewrap-all", action="store_true", help="re-wrap every copy on the host")
    g.add_argument("--delete-old", action="store_true", help="delete every copy on the host")
    g.add_argument("--leave-all", action="store_true", help="leave every copy as it is")
    r.set_defaults(func=_rotate_cmd)
    ks.add_parser("unlock", help="unlock the server running on this host").set_defaults(
        func=lambda a: unlock(load(Path(a.config)))
    )


def _verify_cmd(args) -> int:
    from ..store.maintenance import queue_host_event

    config = load(Path(args.config))
    ok = verify(
        config,
        record=lambda kid, ok: queue_host_event(
            config,
            "key.verified" if ok else "key.verify-failed",
            {"fingerprint": master.fingerprint(kid)},
        ),
    )
    return 0 if ok else 1


def _rotate_cmd(args) -> int:
    from ..store.maintenance import queue_host_event

    config = load(Path(args.config))
    running = _running(config)
    flags = {"rewrap": args.rewrap_all, "delete": args.delete_old, "leave": args.leave_all}
    all_copies = next((k for k, on in flags.items() if on), None)
    old_fp, new_fp = rotate(config, running=running, all_copies=all_copies)
    if not running:  # the running server records its own rotation in Activity
        queue_host_event(config, "key.rotated", {"from": old_fp, "to": new_fp})
    return 0

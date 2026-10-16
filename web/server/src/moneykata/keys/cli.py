"""`moneykata keys …` (requirements S15.4, S15.6, S15.7): run on the host as one-off
containers of the same image, or, for `unlock`, against the server running on this host. The
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


def _base(config: Config) -> str:
    scheme = "https" if config.mode == "tls" else "http"
    return f"{scheme}://127.0.0.1:{config.port}"


def _running(config: Config) -> bool:
    """Whether the server is up and unlocked on this host's loopback."""
    import httpx

    try:
        r = httpx.get(f"{_base(config)}/ui/api/unlock", verify=False, timeout=5)  # noqa: S501
    except httpx.HTTPError:
        return False
    return r.status_code == 200 and r.json().get("locked") is False


def rotate(
    config: Config,
    ask: Ask = input,
    say: Say = _say,
    ask_hidden: Ask = _hidden,
    running: bool | None = None,
) -> tuple[str, str]:
    """A new master key re-wraps the data key in one step (S15.7.1): the new phrase shown and
    confirmed, the keyring written with the old key recorded. Through the running server when
    it is up (it holds the data key, so no old phrase is needed: the way out of a lost
    phrase); with the old phrase typed when it is stopped. Nothing else changes."""
    running = _running(config) if running is None else running
    if running:
        new_key = master.new_master()
        say(sheet(new_key, config.name, dt.date.today()))
        say("\nType back three of the words to show they are written down.")
        if not confirm_three(new_key, ask, say):
            raise RefuseStart("the words were not confirmed; the key was not rotated")
        return _rotate_online(config, new_key, say)
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
    new_key = master.new_master()
    say(sheet(new_key, config.name, dt.date.today()))
    say("\nType back three of the words to show they are written down.")
    if not confirm_three(new_key, ask, say):
        raise RefuseStart("the words were not confirmed; the key was not rotated")
    master.write_keyring(
        config.keyring_path, master.rotated(ring, data_key, new_key, master.now()), _owner()
    )
    old_fp, new_fp = master.fingerprint(old_key), master.fingerprint(new_key)
    _said_rotated(say, old_fp, new_fp)
    return old_fp, new_fp


def _rotate_online(config: Config, new_key: bytes, say: Say) -> tuple[str, str]:
    import httpx

    base = _base(config)
    # This container's own listener on loopback; its certificate may be self-signed.
    r = httpx.post(
        f"{base}/ui/api/keys/rotate",
        json={"phrase": " ".join(phrase.to_words(new_key))},
        headers={"Origin": base},
        verify=False,  # noqa: S501
        timeout=300,
    )
    if r.status_code != 200:
        raise RefuseStart(f"the server refused the rotation: {r.json().get('detail', r.text)}")
    out = r.json()
    _said_rotated(say, out["from"], out["to"])
    return out["from"], out["to"]


def _said_rotated(say: Say, old_fp: str, new_fp: str) -> None:
    say(f"Rotated: {old_fp} → {new_fp}. Back up the new phrase now.")
    say(
        "The server unlocks with the new phrase from its next start. Keep the old phrase until "
        "every copy made before today is gone (S15.7.1)."
    )


def unlock(config: Config, ask: Ask = _hidden, say: Say = _say) -> int:
    """`moneykata keys unlock` (S15.4.3): the phrase handed to the server running on this
    host, over its own listener on loopback, the way the unlock page hands it over."""
    import httpx

    words = ask("recovery phrase (12 words): ")
    try:
        phrase.from_words(words)
    except phrase.PhraseError as e:
        say(f"refused: not a valid phrase: {e}")
        return 1
    base = _base(config)
    try:
        # This container's own listener on loopback; its certificate may be self-signed.
        r = httpx.post(
            f"{base}/ui/api/unlock",
            json={"phrase": words},
            headers={"Origin": base},
            verify=False,  # noqa: S501
            timeout=300,
        )
    except httpx.HTTPError as e:
        say(f"refused: the server isn't answering on {base}: {e}")
        return 1
    if r.status_code == 200:
        say(f"unlocked: {r.json().get('fingerprint', '')}")
        return 0
    detail = r.json().get("detail", r.text) if r.headers.get("content-type") else r.text
    say(f"refused: {detail}")
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
    ks.add_parser(
        "rotate", help="a new master key and phrase: through the running server, or offline"
    ).set_defaults(func=_rotate_cmd)
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
    old_fp, new_fp = rotate(config, running=running)
    if not running:  # the running server records its own rotation in Activity
        queue_host_event(config, "key.rotated", {"from": old_fp, "to": new_fp})
    return 0

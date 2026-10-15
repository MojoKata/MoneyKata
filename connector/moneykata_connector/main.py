"""`moneykata-connector` (requirements S18.3, S18.4, S18.7.2): `serve` runs the connector;
`init` makes the vault and its words; the rest talk to the running connector over its socket:
`unlock`, `lock`, `status`, `pair <code>`, `unpair`, `connect <connection id>`, `reset`."""

import argparse
import contextlib
import getpass
import logging
import os
import secrets
import signal
import sys
from pathlib import Path

from . import VERSION, sock, words
from .vault import Vault, VaultError

DATA = Path(os.environ.get("MONEYKATA_CONNECTOR_DATA", "/var/lib/moneykata-connector"))
SOCKET = Path(os.environ.get("MONEYKATA_CONNECTOR_SOCKET", "/run/moneykata-connector/sock"))


def sheet(phrase: list[str], fingerprint: str) -> str:
    rows = [f"  {i:>2}. {w}" for i, w in enumerate(phrase, 1)]
    return "\n".join(
        [
            "MoneyKata Connector vault words",
            "",
            f"  vault:  {fingerprint}",
            "",
            *rows,
            "",
            "Keep them in the household's password manager. They are never stored: the vault",
            "opens only with them, and `reset` is the only way on without them.",
        ]
    )


def confirm_three(phrase: list[str], ask=input, say=print) -> bool:
    for _ in range(3):
        picks = sorted(secrets.SystemRandom().sample(range(12), 3))
        ok = all(
            (t := ask(f"word {i + 1}: ").strip().lower()) == phrase[i]
            or (len(t) >= 4 and phrase[i].startswith(t))
            for i in picks
        )
        if ok:
            return True
        say("That is not right. Check the words and try again.")
    return False


def cmd_init(args) -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    v = Vault(DATA / "vault.json")
    try:
        phrase = v.create()
    except VaultError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 78
    print(sheet(phrase, v.fingerprint()))
    print("\nType back three of the words to show they are written down.")
    if not confirm_three(phrase):
        (DATA / "vault.json").unlink()
        print("refused: the words were not confirmed; no vault was made", file=sys.stderr)
        return 78
    print(f"Made {v.fingerprint()}. Start the connector, then unlock it with the words.")
    return 0


def cmd_serve(args) -> int:
    from .core import Core

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    DATA.mkdir(parents=True, exist_ok=True)
    core = Core(DATA)
    if not core.vault.exists():
        print("refusing to start: no vault; run `moneykata-connector init` first", file=sys.stderr)
        return 78
    sock.serve(core, SOCKET)
    logging.info(
        "MoneyKata Connector %s: locked, %s", VERSION, "paired" if core.pairing else "not paired"
    )
    signal.signal(signal.SIGTERM, lambda *_: core.stop())  # docker stop: a clean exit
    with contextlib.suppress(KeyboardInterrupt):
        core.run_forever()
    logging.info("stopped")
    return 0


def _ask(request: dict) -> dict:
    out = sock.ask(SOCKET, request)
    if "error" in out:
        print(f"refused: {out['error']}", file=sys.stderr)
        raise SystemExit(1)
    return out


def cmd_unlock(args) -> int:
    phrase = getpass.getpass("the vault's 12 words: ")
    try:
        words.from_words(phrase)
    except words.PhraseError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1
    _ask({"command": "unlock", "words": phrase})
    print("unlocked")
    return 0


def cmd_simple(what: str):
    def run(args) -> int:
        out = _ask({"command": what})
        if what == "status":
            for k, v in out.items():
                print(f"{k}: {v}")
        elif what == "reset":
            print(sheet(out["words"], out["fingerprint"]))
        else:
            print(what + "ed" if what != "lock" else "locked")
        return 0

    return run


def cmd_pair(args) -> int:
    out = _ask({"command": "pair", "code": args.code})
    print(f"paired: this connector's fingerprint is {out['fingerprint']}")
    print("Compare it with what MoneyKata shows under Settings › Connector.")
    return 0


def cmd_connect(args) -> int:
    """Credentials typed here, never through MoneyKata (S18.7.2)."""
    creds = {}
    print(f"credentials for {args.id} (empty name ends):")
    while True:
        name = input("field: ").strip()
        if not name:
            break
        creds[name] = getpass.getpass(f"{name}: ")
    _ask({"command": "connect", "id": args.id, "credentials": creds})
    print("filed in the vault")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="moneykata-connector", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the connector (the default)").set_defaults(func=cmd_serve)
    sub.add_parser("init", help="make the vault and show its words").set_defaults(func=cmd_init)
    sub.add_parser("unlock", help="unlock the vault with its words").set_defaults(func=cmd_unlock)
    for what, text in (
        ("lock", "lock the vault"),
        ("status", "what the connector is doing"),
        ("unpair", "forget the paired server and its credentials"),
        ("reset", "a new vault with new words (the old one is lost)"),
    ):
        sub.add_parser(what, help=text).set_defaults(func=cmd_simple(what))
    pr = sub.add_parser("pair", help="pair with MoneyKata, with the code Settings shows")
    pr.add_argument("code")
    pr.set_defaults(func=cmd_pair)
    co = sub.add_parser("connect", help="type a Connection's credentials here")
    co.add_argument("id")
    co.set_defaults(func=cmd_connect)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return getattr(args, "func", cmd_serve)(args)


if __name__ == "__main__":
    sys.exit(main())

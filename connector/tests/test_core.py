"""The connector's core (requirements S18.1–S18.5): the vault and its words, the keys, signed
calls, sealed credentials, the egress allowlist, the socket's commands, and the limits of
S18.1.2 (no import from MoneyKata, the core under 600 lines, a driver under 400)."""

import ast
import json
import re
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from moneykata_connector import client, keys, sealed, signing, sock, vault, words
from moneykata_connector.drivers import registry

PACKAGE = Path(__file__).resolve().parents[1] / "moneykata_connector"


def test_words_round_trip_and_catch_a_wrong_word():
    key = bytes(range(16))
    w = words.to_words(key)
    assert len(w) == 12 and words.from_words(" ".join(w)) == key
    assert words.from_words([x[:4] for x in w]) == key, "the first four letters are enough"
    with pytest.raises(words.PhraseError, match="not in the word list"):
        words.from_words([*w[:-1], "zzzz"])
    with pytest.raises(words.PhraseError, match="check out"):
        words.from_words([*w[:-1], words.wordlist()[(words.wordlist().index(w[-1]) + 1) % 2048]])


def test_the_vault_opens_only_with_its_words_and_waits_after_five_wrong(tmp_path, monkeypatch):
    v = vault.Vault(tmp_path / "vault.json")
    phrase = " ".join(v.create())
    fp = v.fingerprint()
    v.put("Conn_1", {"username": "alice", "password": "pw"})
    v.lock()
    assert v.locked
    with pytest.raises(vault.VaultError, match="locked"):
        v.get("Conn_1")
    other = " ".join(words.to_words(b"\x01" * 16))
    with pytest.raises(vault.VaultError, match="not this vault's"):
        v.unlock(other)
    with pytest.raises(vault.VaultError, match="12 words"):
        v.unlock("just three words")
    v.unlock(phrase)
    assert v.get("Conn_1") == {"username": "alice", "password": "pw"} and v.ids() == ["Conn_1"]
    v.delete("Conn_1")
    assert v.ids() == []
    assert fp == v.fingerprint() and len(fp) == 16
    # The file holds no credential in clear.
    v.put("Conn_2", {"password": "hunter2-secret"})
    assert "hunter2" not in (tmp_path / "vault.json").read_text()
    # Five wrong in a row: the next waits 15 minutes.
    v.lock()
    now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    for _ in range(5):
        with pytest.raises(vault.VaultError):
            v.unlock(other)
    with pytest.raises(vault.VaultError, match="wait"):
        v.unlock(phrase)
    now[0] += 15 * 60 + 1
    v.unlock(phrase)
    assert not v.locked
    # Reset: a new vault, new words, the old credentials gone.
    new = " ".join(v.reset())
    assert new != phrase and v.ids() == []


def test_keys_are_made_at_pairing_the_sealing_key_in_the_vault_and_forgotten(tmp_path):
    assert keys.load(tmp_path / "pairing.json") is None
    private, public = keys.new_sealing_key()
    p = keys.make(tmp_path / "pairing.json", "https://money.lan", "f" * 64, public)
    again = keys.load(tmp_path / "pairing.json")
    assert again.identity_public == p.identity_public and again.address == "https://money.lan"
    assert again.sealing_public == public
    assert keys.short(p.fingerprint).count(" ") == 3
    # The pairing file holds the public half only (S18.4.5): nothing in it opens a box.
    text = (tmp_path / "pairing.json").read_text()
    assert keys.b64(private) not in text and "sealingPublic" in text and '"sealing"' not in text
    v = vault.Vault(tmp_path / "vault.json")
    v.create()
    assert v.sealing_key() is None
    v.keep_sealing_key(private)
    assert v.sealing_key() == private and private.hex() not in (tmp_path / "vault.json").read_text()
    keys.forget(tmp_path / "pairing.json")
    assert keys.load(tmp_path / "pairing.json") is None


def test_credentials_are_bound_to_the_host_they_were_filed_for(tmp_path):
    v = vault.Vault(tmp_path / "vault.json")
    v.create()
    v.put("Conn_1", {"username": "alice", "password": "pw"}, "ofx.cu.example")
    v.put("Conn_2", {"appSecret": "s"})
    assert v.host("Conn_1") == "ofx.cu.example" and v.host("Conn_2") is None
    assert v.get("Conn_1") == {"username": "alice", "password": "pw"} and v.host("Conn_9") is None


def test_signed_calls_and_checked_answers():
    k = Ed25519PrivateKey.generate()
    headers, nonce = signing.sign(k, "POST", "/connector/v1/report", b"{}", "a" * 64)
    assert set(headers) == {"MK-Conn-Key", "MK-Conn-Time", "MK-Conn-Nonce", "MK-Conn-Signature"}
    msg = "\n".join(
        [
            "MK-CONN-1",
            "POST",
            "/connector/v1/report",
            signing.body_hash(b"{}"),
            headers["MK-Conn-Time"],
            nonce,
            "a" * 64,
        ]
    ).encode()
    k.public_key().verify(keys.unb64(headers["MK-Conn-Signature"]), msg)
    server = Ed25519PrivateKey.generate()
    t = str(int(time.time()))
    me, call = "c" * 64, signing.body_hash(b"{}")
    answer = "\n".join(
        ["MK-CONN-1-ANSWER", "200", signing.body_hash(b"ok"), t, nonce, me, call]
    ).encode()
    good = {"MK-Conn-Time": t, "MK-Conn-Signature": keys.b64(server.sign(answer))}
    pub = server.public_key().public_bytes_raw()
    signing.verify_answer(pub, 200, b"ok", nonce, good, me, call)
    with pytest.raises(signing.Refused, match="isn't signed by the server"):
        signing.verify_answer(
            Ed25519PrivateKey.generate().public_key().public_bytes_raw(),
            200,
            b"ok",
            nonce,
            good,
            me,
            call,
        )
    # An answer to another caller, or to another request, is refused (protocol §3.3).
    for who, what in (("d" * 64, call), (me, signing.body_hash(b'{"x":1}'))):
        with pytest.raises(signing.Refused, match="isn't signed by the server"):
            signing.verify_answer(pub, 200, b"ok", nonce, good, who, what)
    with pytest.raises(signing.Refused, match="wasn't signed"):
        signing.verify_answer(pub, 200, b"ok", nonce, {}, me, call)


def test_a_box_sealed_to_the_sealing_key_opens_for_its_connection_only():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    sealing = X25519PrivateKey.generate()
    once = X25519PrivateKey.generate()
    shared = once.exchange(
        X25519PublicKey.from_public_bytes(sealing.public_key().public_bytes_raw())
    )
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"Conn_9", info=sealed.LABEL).derive(
        shared
    )
    nonce = b"\x02" * 12
    box = keys.b64(
        once.public_key().public_bytes_raw()
        + nonce
        + AESGCM(key).encrypt(nonce, b'{"password": "pw"}', None)
    )
    assert sealed.open_box(box, sealing, "Conn_9") == {"password": "pw"}
    with pytest.raises(Exception):  # noqa: B017 - another Connection: another key
        sealed.open_box(box, sealing, "Conn_8")


def test_the_egress_allowlist_refuses_every_other_host():
    e = client.Egress()
    e.allow("money.lan", "api.schwabapi.com")
    e.check("MONEY.lan")
    with pytest.raises(client.EgressRefused):
        e.check("evil.example")
    t = client.Transport(e)
    with pytest.raises(client.EgressRefused):
        t.request("GET", "https://evil.example/x", {}, b"")


def test_every_driver_declares_its_hosts_and_needs():
    for name, d in registry().items():
        assert d.name == name
        assert isinstance(d.hosts, tuple) and isinstance(d.needs, tuple)
        assert d.interval >= 60


def _code_lines(path: Path) -> int:
    """Lines of code: not blank, not a comment, not a docstring."""
    text = path.read_text()
    tree = ast.parse(text)
    doc_lines = set()
    for node in ast.walk(tree):
        kinds = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        first = node.body[0] if isinstance(node, kinds) and node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            doc_lines |= set(range(first.lineno, first.end_lineno + 1))
    return sum(
        1
        for n, line in enumerate(text.splitlines(), 1)
        if line.strip() and not line.strip().startswith("#") and n not in doc_lines
    )


def test_the_core_and_each_driver_stay_small_and_import_nothing_from_moneykata():
    """S18.1.2: the core under 1,000 lines of code, a driver under 400, no import from
    MoneyKata."""
    core = [p for p in PACKAGE.glob("*.py")]
    total = sum(_code_lines(p) for p in core)
    assert total <= 1000, f"the core is {total} lines of code"
    for p in (PACKAGE / "drivers").glob("*.py"):
        assert _code_lines(p) <= 400, f"{p.name} is {_code_lines(p)} lines of code"
    for p in PACKAGE.rglob("*.py"):
        assert not re.search(r"^\s*(from|import)\s+moneykata\b", p.read_text(), re.M), p


def test_the_socket_commands_talk_to_the_running_connector(tmp_path):
    from moneykata_connector.core import ConnectionState, Core

    core = Core(tmp_path, transport=client.Transport(client.Egress()))
    phrase = " ".join(core.vault.create())
    core.vault.lock()
    path = tmp_path / "sock"
    sock.serve(core, path)
    assert sock.ask(path, {"command": "status"})["locked"] is True
    assert "error" in sock.ask(path, {"command": "unlock", "words": "bad words"})
    # Pairing needs the vault open: the sealing key goes into it.
    assert "unlock the vault first" in sock.ask(path, {"command": "pair", "code": "x"})["error"]
    assert sock.ask(path, {"command": "unlock", "words": phrase})["locked"] is False
    # Credentials typed here are filed for a Connection the connector knows, bound to the
    # host its settings name (S18.7.3); an unknown one is refused.
    out = sock.ask(path, {"command": "connect", "id": "Conn_1", "credentials": {"a": "b"}})
    assert "hasn't heard of that Connection" in out["error"]
    core.connections["Conn_1"] = ConnectionState(
        "Conn_1", "ofx-direct", "CU", {"url": "https://ofx.cu.example/x"}, []
    )
    assert sock.ask(path, {"command": "connect", "id": "Conn_1", "credentials": {"a": "b"}})["ok"]
    assert core.vault.get("Conn_1") == {"a": "b"} and core.vault.host("Conn_1") == "ofx.cu.example"
    assert sock.ask(path, {"command": "lock"})["locked"] is True
    out = sock.ask(path, {"command": "reset"})
    assert len(out["words"]) == 12 and json.loads((tmp_path / "vault.json").read_text())["format"]
    assert "error" in sock.ask(path, {"command": "nothing"})


def test_a_changed_server_address_sends_nothing_and_asks_for_the_credentials_again(tmp_path):
    """S18.7.3: the host a credential was filed for is the only one it is ever sent to."""
    from moneykata_connector.core import ConnectionState, Core
    from moneykata_connector.drivers.ofx_direct import OfxDirect

    sent = []

    class Watching(client.Transport):
        def request(self, method, url, headers, body, pins=None):
            sent.append(url)
            return client.Answer(200, {}, b"<SONRS><CODE>0</SONRS><ACCTID>1204")

    core = Core(tmp_path, transport=Watching(client.Egress()), drivers={"ofx-direct": OfxDirect()})
    core.vault.create()
    c = core.connections["Conn_1"] = ConnectionState(
        "Conn_1", "ofx-direct", "CU", {"url": "https://ofx.cu.example/ofx", "accountId": "1204"}, []
    )
    core.vault.put("Conn_1", {"username": "alice", "password": "pw"}, "ofx.cu.example")
    core._run(c)
    assert sent == ["https://ofx.cu.example/ofx"] and c.state == "ok"
    # MoneyKata's next answer names another server: the password never goes there.
    c.settings = {**c.settings, "url": "https://evil.example/ofx"}
    core._run(c)
    assert sent == ["https://ofx.cu.example/ofx"]
    assert c.state == "needs-sign-in" and "changed from ofx.cu.example to evil.example" in c.message
    assert core.vault.get("Conn_1") is None, "the old credentials are gone with their binding"


def test_a_driver_run_reaches_its_own_hosts_and_no_other(tmp_path):
    # N17: each run is held to its driver's declared hosts; another driver's, or MoneyKata's,
    # is refused (S18.1.2).
    from urllib.parse import urlsplit

    from moneykata_connector.core import ConnectionState, Core
    from moneykata_connector.drivers import Driver, Result
    from moneykata_connector.drivers.schwab import Schwab

    asked = []

    class Checking(client.Transport):
        def request(self, method, url, headers, body, pins=None):
            host = urlsplit(url).hostname or ""
            self.egress.check(host)
            asked.append(host)
            return client.Answer(200, {}, b"{}")

    class Greedy(Driver):
        name = "greedy"
        label = "Greedy"
        hosts = ("own.example",)

        def run(self, settings, credentials, accounts, transport):
            transport.request("GET", "https://own.example/statement", {}, b"")
            transport.request("GET", settings["then"], {}, b"")
            return Result("ok", "")

    core = Core(
        tmp_path,
        transport=Checking(client.Egress()),
        drivers={"greedy": Greedy(), "schwab": Schwab()},
    )
    core.egress.allow("money.lan")
    core.vault.create()
    for then in ("https://api.schwabapi.com/x", "https://money.lan/connector/v1/files"):
        c = ConnectionState("Conn_1", "greedy", "Own", {"then": then}, [])
        core._run(c)
        assert c.state == "failing" and "refused" in c.message, c.message
    assert asked == ["own.example", "own.example"]
    for d in core.drivers.values():
        own = client.Egress()
        own.allow(*d.hosts_for({}))
        for other in core.drivers.values():
            for host in set(other.hosts) - set(d.hosts):
                with pytest.raises(client.EgressRefused):
                    own.check(host)

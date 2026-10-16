import os

import pytest

from moneykata.config import RefuseStart
from moneykata.keys import cli, master, phrase
from moneykata.store import maintenance


def test_phrase_matches_bip39_vectors():
    assert phrase.to_words(bytes(16)) == ["abandon"] * 11 + ["about"]
    assert " ".join(phrase.to_words(bytes([0x7F] * 16))) == (
        "legal winner thank year wave sausage worth useful legal winner thank yellow"
    )
    assert " ".join(phrase.to_words(bytes([0x80] * 16))) == (
        "letter advice cage absurd amount doctor acoustic avoid letter advice cage above"
    )


def test_phrase_reads_back_with_four_letter_prefixes_and_any_case():
    key = os.urandom(16)
    words = phrase.to_words(key)
    assert phrase.from_words(" ".join(words).upper()) == key
    assert phrase.from_words([w[:4] for w in words]) == key


def test_phrase_catches_mistakes():
    words = phrase.to_words(bytes(16))
    with pytest.raises(phrase.PhraseError, match="12 words"):
        phrase.from_words(words[:11])
    with pytest.raises(phrase.PhraseError, match="not in the word list"):
        phrase.from_words(["zzzz", *words[1:]])
    with pytest.raises(phrase.PhraseError, match="do not check out"):
        phrase.from_words(["zoo", *words[1:]])


def test_fingerprint_form():
    fp = master.fingerprint(bytes(16))
    assert fp.startswith("mk-") and "…" in fp and len(fp) == 12
    assert master.key_id(bytes(16)) == master.key_id(bytes(16))


def test_init_writes_only_the_keyring_and_refuses_a_second_time(keyed_config, master_key, tmp_path):
    """S15.4: the master key is the phrase; nothing but the wrapped data key is written."""
    ring = keyed_config.keyring_path
    assert ring.exists() and os.stat(ring).st_mode & 0o777 == 0o600
    written = {p.name for p in tmp_path.rglob("*") if p.is_file()}
    assert written == {"keyring"}
    assert master_key.hex() not in ring.read_text()
    assert " ".join(phrase.to_words(master_key)) not in ring.read_text()
    with pytest.raises(RefuseStart, match="already exists"):
        cli.init(keyed_config, say=lambda _: None, confirm=False)
    assert master.unlock_keys(keyed_config, master_key).master_id == master.key_id(master_key)
    assert cli.fingerprint_of(keyed_config) == master.fingerprint(master_key)


def test_a_wrong_phrase_does_not_unlock_the_keys(keyed_config):
    with pytest.raises(master.WrongPhrase, match="wrapped by"):
        master.unlock_keys(keyed_config, os.urandom(16))


def test_init_waits_for_three_words(config):
    answers = iter(["wrong", "wrong", "wrong"] * 3)
    with pytest.raises(RefuseStart, match="not confirmed"):
        cli.init(config, ask=lambda _: next(answers), say=lambda _: None)
    assert not config.keyring_path.exists()


def test_init_saves_when_the_words_are_right(config, monkeypatch):
    made = {}
    real = master.new_master
    monkeypatch.setattr(master, "new_master", lambda: made.setdefault("k", real()))

    def ask(prompt):
        n = int(prompt.split()[1].rstrip(":"))
        return phrase.to_words(made["k"])[n - 1][:4]

    key = cli.init(config, ask=ask, say=lambda _: None)
    assert master.unlock_keys(config, key).master_id == master.key_id(key)


def test_verify_compares_without_changing_anything(keyed_config, master_key):
    seen = []
    before = keyed_config.keyring_path.read_bytes()
    assert cli.verify(
        keyed_config,
        ask=lambda _: " ".join(phrase.to_words(master_key)),
        say=lambda _: None,
        record=lambda kid, ok: seen.append(ok),
    )
    assert not cli.verify(
        keyed_config,
        ask=lambda _: " ".join(phrase.to_words(bytes(16))),
        say=lambda _: None,
        record=lambda kid, ok: seen.append(ok),
    )
    assert not cli.verify(keyed_config, ask=lambda _: "three words only", say=lambda _: None)
    assert seen == [True, False] and keyed_config.keyring_path.read_bytes() == before


def test_host_commands_queue_what_they_did_for_activity(keyed_config):
    """A one-off container has no phrase to open the database with: what it did waits in a
    queue the server takes at its next unlock (S15.7.4)."""
    maintenance.queue_host_event(keyed_config, "key.verified", {"fingerprint": "mk-1"})
    maintenance.queue_host_event(keyed_config, "key.rotated", {"from": "mk-1", "to": "mk-2"})
    queued = keyed_config.data_dir / maintenance.HOST_EVENTS
    assert os.stat(queued).st_mode & 0o777 == 0o600
    taken = maintenance.take_host_events(keyed_config)
    assert [e["kind"] for e in taken] == ["key.verified", "key.rotated"]
    assert taken[1]["detail"] == {"from": "mk-1", "to": "mk-2"} and taken[0]["at"]
    assert not queued.exists() and maintenance.take_host_events(keyed_config) == []


def _rotate(config, old_key, monkeypatch):
    """Rotate offline: the old phrase typed and the new one's words typed back."""
    made = {}
    real = master.new_master

    def remember():
        made["k"] = real()
        return made["k"]

    monkeypatch.setattr(master, "new_master", remember)

    def ask(prompt):
        n = int(prompt.split()[1].rstrip(":"))
        return phrase.to_words(made["k"])[n - 1]

    out = cli.rotate(
        config,
        ask=ask,
        say=lambda _: None,
        ask_hidden=lambda _: " ".join(phrase.to_words(old_key)),
        running=False,
        all_copies="rewrap",
    )
    return out, made["k"]


def test_rotate_offline_rewraps_and_records_the_previous_key_in_the_keyring(
    config, monkeypatch, tmp_path
):
    old_key = cli.init(config, say=lambda _: None, confirm=False)
    old = master.unlock_keys(config, old_key)
    (old_fp, new_fp), new_key = _rotate(config, old_key, monkeypatch)
    ring = master.read_keyring(config.keyring_path)
    assert [master.fingerprint(p.master_id) for p in ring.previous] == [old_fp]
    new = master.unlock_keys(config, new_key)
    assert new.keys.database == old.keys.database  # the data key itself is unchanged
    assert master.fingerprint(new.master_id) == new_fp != old_fp
    with pytest.raises(master.WrongPhrase):
        master.unlock_keys(config, old_key)
    # Nothing of either phrase was written anywhere.
    for p in tmp_path.rglob("*"):
        if p.is_file():
            text = p.read_bytes()
            assert old_key not in text and new_key not in text, p


def test_rotate_offline_refuses_a_wrong_phrase_or_a_pending_reencryption(config, monkeypatch):
    cli.init(config, say=lambda _: None, confirm=False)
    before = config.keyring_path.read_bytes()
    with pytest.raises(RefuseStart, match="not this server's key"):
        _rotate(config, os.urandom(16), monkeypatch)
    assert config.keyring_path.read_bytes() == before
    cli.pending_reencrypt(config).write_text("{}")
    with pytest.raises(RefuseStart, match="re-encryption is pending"):
        cli.rotate(
            config, ask=lambda _: "", say=lambda _: None, ask_hidden=lambda _: "", running=False
        )


def test_rotate_through_the_running_server_needs_no_old_phrase(store, keyed_config, master_key):
    """S15.7.1: the running server holds the data key, so a lost phrase can be replaced while
    it is up; the keyring records the old key."""
    new_key = os.urandom(16)
    store2, outcomes = maintenance.rotate_running(keyed_config, store, new_key)
    assert outcomes == {}
    assert store2.keys.master_id == master.key_id(new_key) and store2.db is store.db
    ring = master.read_keyring(keyed_config.keyring_path)
    assert [p.master_id for p in ring.previous] == [master.key_id(master_key)]
    assert master.unlock_keys(keyed_config, new_key).keys.database == store.keys.keys.database
    with pytest.raises(master.WrongPhrase):
        master.unlock_keys(keyed_config, master_key)
    maintenance.next_keyring(keyed_config).write_text("{}")
    with pytest.raises(RefuseStart, match="re-encryption is pending"):
        maintenance.rotate_running(keyed_config, store2, os.urandom(16))


def test_rotate_offline_rewraps_the_copies_on_the_host(
    store, keyed_config, master_key, monkeypatch
):
    """S15.7.1: offline, with the old phrase typed, every copy's keyring is re-wrapped too."""
    b = maintenance.backup(keyed_config, store)
    store.db.dispose()
    (_old_fp, _new_fp), new_key = _rotate(keyed_config, master_key, monkeypatch)
    assert maintenance.verify_backup(keyed_config, new_key) == b
    with pytest.raises(RefuseStart):
        maintenance.verify_backup(keyed_config, master_key)
    # Asked per copy: Enter re-wraps, 'd' deletes, 'l' leaves.
    answers = iter(["", "d", "l"])
    found = [
        {"name": n, "kind": "backup", "made": "2026-10-01T00:00:00", "bytes": 0, "opens": "current"}
        for n in ("a", "b", "c")
    ]
    assert cli.ask_copies(found, ask=lambda _: next(answers), say=lambda _: None) == {
        "a": "rewrap",
        "b": "delete",
        "c": "leave",
    }

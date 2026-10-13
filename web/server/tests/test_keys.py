import os

import pytest

from moneykata.config import RefuseStart, load
from moneykata.keys import cli, master, phrase


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


def test_init_writes_a_0400_key_and_refuses_to_overwrite(keyed_config):
    st = os.stat(keyed_config.key_file)
    assert st.st_mode & 0o777 == 0o400
    assert st.st_size == 16
    with pytest.raises(RefuseStart, match="never overwrites"):
        cli.init(keyed_config, say=lambda _: None, confirm=False)
    master.open_keys(keyed_config)


@pytest.mark.parametrize(
    "damage, reason",
    [
        (lambda p: os.chmod(p, 0o644), "read by others"),
        (lambda p: os.chmod(p, 0o600), "written by an account"),
        (lambda p: (os.chmod(p, 0o600), p.write_bytes(b"x" * 15), os.chmod(p, 0o400)), "16 bytes"),
        (lambda p: p.unlink(), "does not exist"),
    ],
)
def test_start_refuses_a_bad_key_file(keyed_config, damage, reason):
    damage(keyed_config.key_file)
    with pytest.raises(RefuseStart, match=reason):
        master.open_keys(keyed_config)


def test_start_refuses_a_key_that_does_not_unwrap(keyed_config):
    os.chmod(keyed_config.key_file, 0o600)
    keyed_config.key_file.write_bytes(os.urandom(16))
    os.chmod(keyed_config.key_file, 0o400)
    with pytest.raises(RefuseStart, match="wrapped by"):
        master.open_keys(keyed_config)


def test_init_waits_for_three_words(config):
    answers = iter(["wrong", "wrong", "wrong"] * 3)
    with pytest.raises(RefuseStart, match="not confirmed"):
        cli.init(config, ask=lambda _: next(answers), say=lambda _: None)
    assert not config.key_file.exists()
    assert not config.keyring_path.exists()


def test_init_saves_when_the_words_are_right(config, monkeypatch):
    made = {}
    real = master.new_master
    monkeypatch.setattr(master, "new_master", lambda: made.setdefault("k", real()))

    def ask(prompt):
        n = int(prompt.split()[1].rstrip(":"))
        return phrase.to_words(made["k"])[n - 1][:4]

    key = cli.init(config, ask=ask, say=lambda _: None)
    assert master.open_keys(config).master_id == master.key_id(key)


def test_from_phrase_writes_the_key_back(keyed_config):
    key = keyed_config.key_file.read_bytes()
    os.chmod(keyed_config.key_file, 0o600)
    keyed_config.key_file.unlink()
    words = " ".join(phrase.to_words(key))
    cli.init(keyed_config, ask=lambda _: words, say=lambda _: None, from_phrase=True)
    master.open_keys(keyed_config)
    other = " ".join(phrase.to_words(bytes(16)))
    os.chmod(keyed_config.key_file, 0o600)
    keyed_config.key_file.unlink()
    with pytest.raises(RefuseStart, match="wrapped by"):
        cli.init(keyed_config, ask=lambda _: other, say=lambda _: None, from_phrase=True)


def test_verify_compares_without_changing_anything(keyed_config):
    key = keyed_config.key_file.read_bytes()
    seen = []
    assert cli.verify(
        keyed_config,
        ask=lambda _: " ".join(phrase.to_words(key)),
        say=lambda _: None,
        record=lambda kid, ok: seen.append(ok),
    )
    assert not cli.verify(
        keyed_config,
        ask=lambda _: " ".join(phrase.to_words(bytes(16))),
        say=lambda _: None,
        record=lambda kid, ok: seen.append(ok),
    )
    assert seen == [True, False]


def test_rotate_rewraps_and_records_the_previous_key(tmp_path):
    toml = tmp_path / "moneykata.toml"
    toml.write_text(f"""[server]
name = "t"
[paths]
data = "{tmp_path / "data"}"
backups = "{tmp_path / "backups"}"
[keys]
master = "{tmp_path / "keys" / "master.key"}"
""")
    config = load(toml)
    cli.init(config, say=lambda _: None, confirm=False)
    old = master.open_keys(config)
    made = {}
    real = master.new_master
    import moneykata.keys.master as m

    def remember():
        made["k"] = real()
        return made["k"]

    m.new_master, saved = remember, m.new_master
    try:

        def ask(prompt):
            n = int(prompt.split()[1].rstrip(":"))
            return phrase.to_words(made["k"])[n - 1]

        old_fp, new_fp = cli.rotate(config, ask=ask, say=lambda _: None)
    finally:
        m.new_master = saved
    config2 = load(toml)
    assert len(config2.previous_keys) == 1
    assert config2.previous_keys[0].fingerprint == old_fp
    assert config2.previous_keys[0].path.exists()
    new = master.open_keys(config2)
    assert new.keys.database == old.keys.database  # the data key itself is unchanged
    assert master.fingerprint(new.master_id) == new_fp != old_fp


def test_rotate_refuses_before_changing_anything_when_the_config_is_read_only(tmp_path):
    toml = tmp_path / "moneykata.toml"
    toml.write_text(f"""[server]
name = "t"
[paths]
data = "{tmp_path / "data"}"
backups = "{tmp_path / "backups"}"
[keys]
master = "{tmp_path / "keys" / "master.key"}"
""")
    config = load(toml)
    cli.init(config, say=lambda _: None, confirm=False)
    before = {p.name: p.read_bytes() for p in (config.key_file, config.keyring_path)}
    toml.chmod(0o444)
    try:
        if os.access(toml, os.W_OK):
            pytest.skip("running as root: a read-only mode does not stop writes")
        with pytest.raises(RefuseStart, match="not writable"):
            cli.rotate(config, ask=lambda _: "", say=lambda _: None)
    finally:
        toml.chmod(0o644)
    assert sorted(p.name for p in config.key_file.parent.iterdir()) == ["master.key"]
    assert {p.name: p.read_bytes() for p in (config.key_file, config.keyring_path)} == before

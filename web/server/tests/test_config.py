from pathlib import Path

import pytest

from moneykata.config import RefuseStart, load, parse
from moneykata.main import main

BASE = {
    "server": {"name": "home", "mode": "proxy", "trusted_proxies": ["10.0.0.0/8"]},
    "paths": {"data": "/var/lib/moneykata", "backups": "/var/backups/moneykata"},
    "keys": {"master": "/etc/moneykata/master.key"},
}


def test_parses_a_full_config():
    c = parse(BASE, "test")
    assert c.name == "home"
    assert c.mode == "proxy"
    assert c.port == 37373
    assert str(c.trusted_proxies[0]) == "10.0.0.0/8"
    assert c.db_path == Path("/var/lib/moneykata/moneykata.db")
    assert c.mail_dir == Path("/var/lib/moneykata/mail")


@pytest.mark.parametrize(
    "change, reason",
    [
        ({"server": {"mode": "open"}}, "server.mode"),
        ({"server": {"port": 0}}, "server.port"),
        ({"server": {"trusted_proxies": ["nope"]}}, "trusted_proxies"),
        ({"keys": {"master": "/var/lib/moneykata/master.key"}}, "inside the data directory"),
        ({"keys": {"master": "/var/backups/moneykata/k"}}, "inside the backup directory"),
        ({"paths": {"data": "relative", "backups": "/b"}}, "absolute"),
        ({"tls": {"cert": "/a.crt"}}, "both cert and key"),
        ({"extra": {}}, "unknown section"),
    ],
)
def test_refuses_what_an_operator_must_fix(change, reason):
    raw = {k: dict(v) for k, v in BASE.items()}
    for k, v in change.items():
        raw.setdefault(k, {}).update(v)
    with pytest.raises(RefuseStart, match=reason):
        parse(raw, "test")


def test_missing_or_broken_file_refuses(tmp_path):
    with pytest.raises(RefuseStart, match="does not exist"):
        load(tmp_path / "none.toml")
    bad = tmp_path / "bad.toml"
    bad.write_text("[server\n")
    with pytest.raises(RefuseStart, match="not valid TOML"):
        load(bad)


def test_refused_start_exits_78_with_one_line(tmp_path, capsys):
    code = main(["--config", str(tmp_path / "none.toml"), "serve"])
    assert code == 78
    err = capsys.readouterr().err.strip().splitlines()
    assert err[-1].startswith("refusing to start: ")

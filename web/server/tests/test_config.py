from pathlib import Path

import pytest

from moneykata.config import RefuseStart, load, parse
from moneykata.main import main

BASE = {
    "server": {"name": "home", "mode": "proxy", "trusted_proxies": ["10.0.0.0/8"]},
    "paths": {"data": "/var/lib/moneykata", "backups": "/var/backups/moneykata"},
}


def test_parses_a_full_config():
    c = parse(BASE, "test")
    assert c.name == "home"
    assert c.mode == "proxy"
    assert c.port == 37373
    assert str(c.trusted_proxies[0]) == "10.0.0.0/8"
    assert c.db_path == Path("/var/lib/moneykata/moneykata.db")
    assert c.mail_dir == Path("/var/lib/moneykata/mail")
    assert c.keyring_path == Path("/var/lib/moneykata/keyring")


@pytest.mark.parametrize(
    "change, reason",
    [
        ({"server": {"mode": "open"}}, "server.mode"),
        ({"server": {"port": 0}}, "server.port"),
        ({"server": {"trusted_proxies": ["nope"]}}, "trusted_proxies"),
        ({"keys": {"master": "/etc/moneykata/master.key"}}, "is not used"),
        ({"paths": {"data": "/d", "backups": "/d/backups"}}, "inside the data directory"),
        ({"paths": {"data": "relative", "backups": "/b"}}, "absolute"),
        ({"tls": {"cert": "/a.crt"}}, "both cert and key"),
        ({"tls": {"names": "money.lan"}}, "list of host names"),
        ({"extra": {}}, "unknown section"),
        ({"server": {"trusted_proxy": ["10.0.0.1"]}}, "unknown key server.trusted_proxy"),
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
    assert main(["--config", str(tmp_path / "none.toml"), "keys", "fingerprint"]) == 78
    assert capsys.readouterr().err.strip().splitlines()[-1].startswith("refused: ")


def test_a_connection_is_not_closed_after_a_thousand_requests(tmp_path):
    """Over HTTP/2 everything a browser asks travels on one connection; Hypercorn's default
    cap of 1,000 requests closed it under the live stream and stranded requests in flight."""
    from moneykata.listener import hypercorn_config
    from moneykata.main import dev_config

    hc = hypercorn_config(dev_config(37373, stubs=False, peer=False, base=tmp_path))
    assert hc.keep_alive_max_requests >= 1_000_000


def test_dev_hostnames_join_the_self_signed_certificate_which_is_remade_to_cover_them(tmp_path):
    """Testing from another machine (web/dev.md): the certificate names what the browser uses."""
    from moneykata.listener import _covers, hypercorn_config
    from moneykata.main import dev_config

    hypercorn_config(dev_config(37373, stubs=False, peer=False, base=tmp_path))
    cert = tmp_path / "data" / "tls" / "self-signed.crt"
    assert _covers(cert) == {"localhost", "127.0.0.1"}
    first = cert.read_bytes()

    config = dev_config(
        37373, False, False, tmp_path, listen="0.0.0.0", hostnames=("moneykata.loco", "10.0.0.5")
    )
    hc = hypercorn_config(config)
    assert hc.bind == ["0.0.0.0:37373"]
    assert _covers(cert) == {"moneykata.loco", "10.0.0.5", "localhost", "127.0.0.1"}
    second = cert.read_bytes()
    assert second != first

    hypercorn_config(dev_config(37373, stubs=False, peer=False, base=tmp_path))
    assert cert.read_bytes() == second  # a certificate that covers more is kept


def test_tls_names_join_the_self_signed_certificate(tmp_path):
    """tls mode on a local network: the certificate also names what the browser uses."""
    import dataclasses

    from moneykata.listener import _covers, hypercorn_config

    raw = {k: dict(v) for k, v in BASE.items()}
    raw["server"]["mode"] = "tls"
    raw["paths"] = {"data": str(tmp_path / "data"), "backups": str(tmp_path / "backups")}
    raw["tls"] = {"names": ["money.lan", "192.168.1.20"]}
    config = parse(raw, "test")
    assert config.cert_names == ("money.lan", "192.168.1.20")
    hypercorn_config(dataclasses.replace(config, host="127.0.0.1"))
    cert = tmp_path / "data" / "tls" / "self-signed.crt"
    assert _covers(cert) == {"money.lan", "192.168.1.20", "home", "localhost"}


def test_dev_mode_runs_only_from_a_checkout(tmp_path, monkeypatch):
    # S17.6: the image carries no dev.sh, and leaves dev mode's code out.
    from moneykata import main as entry
    from moneykata import paths
    from moneykata.config import Config

    config = Config(
        name="t", mode="proxy", data_dir=tmp_path / "data", backup_dir=tmp_path / "b", dev=True
    )
    entry.refuse_dev(config)  # this checkout
    monkeypatch.setattr(paths, "WEB", tmp_path)
    with pytest.raises(RefuseStart, match="only from a checkout"):
        entry.refuse_dev(config)
    dockerfile = (paths.ROOT / "web" / "install" / "Dockerfile").read_text()
    assert "rm -rf src/moneykata/dev" in dockerfile

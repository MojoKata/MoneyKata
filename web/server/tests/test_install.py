"""The image and the compose files keep what requirements S17.8, S15.4 and S13.6 promise:
the unprivileged user, the port, the mounts, the read-only key directory, the health check and
the restart policy. Checked on the files themselves, so a tag or a path can't
drift from the server's own constants."""

import re
import tomllib

import yaml

from moneykata import config, paths
from moneykata.dev import wheels
from moneykata.keys.cli import SERVER_UID

INSTALL = paths.WEB / "install"
REGISTRY = "ghcr.io/mojokata"  # where releases are published (S17.8.2)
DOCKERFILE = (INSTALL / "Dockerfile").read_text()
COMPOSE = {
    name: yaml.safe_load((INSTALL / name).read_text())
    for name in ("compose.yaml", "compose.tls.yaml")
}
EXAMPLE = config.parse(tomllib.loads((INSTALL / "moneykata.toml").read_text()), "moneykata.toml")


def _mounts(service: dict) -> dict[str, tuple[str, bool]]:
    """{container path: (host path, read only)} of a service's bind mounts."""
    out = {}
    for volume in service.get("volumes", []):
        host, target, *flags = volume.split(":")
        out[target] = (host, "ro" in flags)
    return out


def test_the_image_runs_as_the_server_account_on_its_port():
    assert f"USER {SERVER_UID}:{SERVER_UID}" in DOCKERFILE
    assert f"useradd --uid {SERVER_UID} --gid {SERVER_UID}" in DOCKERFILE
    assert f"EXPOSE {config.DEFAULT_PORT}" in DOCKERFILE
    assert 'ENTRYPOINT ["moneykata"]' in DOCKERFILE and 'CMD ["serve"]' in DOCKERFILE
    assert re.search(r'HEALTHCHECK .*\n\s+CMD \["moneykata", "health"\]', DOCKERFILE)


def test_the_image_is_built_from_pinned_sources():
    """A base pinned by digest, the build tool pinned with hashes, and no secret or dev file in
    the build context (S13.7.11, S15.4.5)."""
    base = rf"^ARG PYTHON=python:3\.{wheels.MINOR}-[\w.-]+@sha256:[0-9a-f]{{64}}$"
    assert re.search(base, DOCKERFILE, re.M), "the base image must be the project's Python"
    requirements = (INSTALL / "build-requirements.txt").read_text()
    assert "--hash=sha256:" in requirements
    assert "--require-hashes" in DOCKERFILE
    ignored = (paths.ROOT / ".dockerignore").read_text().split()
    for entry in (".git", "**/.venv", "web/.dev"):
        assert entry in ignored, f".dockerignore must leave out {entry}"


def test_the_image_makes_the_directories_the_example_config_names():
    data, backups = EXAMPLE.data_dir, EXAMPLE.backup_dir
    assert f"install -d -o {SERVER_UID} -g {SERVER_UID} -m 0700 {data} {backups}" in DOCKERFILE
    assert EXAMPLE.mode == "proxy" and EXAMPLE.port == config.DEFAULT_PORT


def test_every_compose_service_runs_the_image_of_this_version():
    tags = {
        f"{REGISTRY}/moneykata:{paths.version()}",
        f"{REGISTRY}/moneykata-connector:{paths.version()}",
    }
    for name, compose in COMPOSE.items():
        for service, spec in compose["services"].items():
            assert spec["image"] in tags, f"{name}: {service} runs {spec['image']}"
        assert compose["services"]["connector"]["image"].startswith(
            f"{REGISTRY}/moneykata-connector:"
        )


def test_the_connector_service_is_apart_locked_down_and_reaches_nothing_in():
    """Its own volume that MoneyKata never mounts, no published port, read only, all
    capabilities dropped (S18.2.1, S18.10); its socket on a tmpfs inside the container."""
    for name, compose in COMPOSE.items():
        c = compose["services"]["connector"]
        assert "ports" not in c and c["restart"] == "unless-stopped", name
        assert c["read_only"] is True and c["cap_drop"] == ["ALL"], name
        assert "no-new-privileges:true" in c["security_opt"], name
        assert any(x.startswith("/run/moneykata-connector:uid=10002") for x in c["tmpfs"]), name
        mounts = _mounts(c)
        assert "/var/lib/moneykata-connector" in mounts, name
        assert mounts["/var/lib/moneykata-connector"][0] == "connector-data", name
        assert "connector-data" in compose["volumes"], name
        server = _mounts(compose["services"]["moneykata"])
        assert not any(h == "connector-data" for h, _ in server.values()), name
        for h, _ in mounts.values():
            assert h not in {h2 for h2, _ in server.values()}, f"{name}: a mount shared"
    dockerfile = (paths.ROOT / "connector" / "Dockerfile").read_text()
    assert "USER 10002:10002" in dockerfile and "EXPOSE" not in dockerfile
    assert re.search(r"^ARG PYTHON=python:3\.14-[\w.-]+@sha256:[0-9a-f]{64}$", dockerfile, re.M)
    assert "--require-hashes" in dockerfile


def test_the_server_service_is_locked_down_and_mounts_no_key():
    """The master key is a phrase, never a file (S15.4): nothing named keys is mounted."""
    for name, compose in COMPOSE.items():
        service = compose["services"]["moneykata"]
        assert service["read_only"] is True, name
        assert service["cap_drop"] == ["ALL"], name
        assert "no-new-privileges:true" in service["security_opt"], name
        assert "/tmp" in service["tmpfs"], name
        # Back after every reboot, locked: a server stopped by a shutdown exited cleanly, which
        # on-failure would leave down (S13.6).
        assert service["restart"] == "unless-stopped", name
        mounts = _mounts(service)
        assert mounts[str(config.DEFAULT_CONFIG)][1], f"{name}: moneykata.toml must be read only"
        assert not mounts[str(EXAMPLE.data_dir)][1] and not mounts[str(EXAMPLE.backup_dir)][1]
        # And the host's time zone, read only, which backups and daily emails follow (S14.9.2).
        assert mounts["/etc/localtime"] == ("/etc/localtime", True), name
        assert service["environment"]["TZ"] == "${TZ:-}", name
        assert set(mounts) == {
            str(EXAMPLE.data_dir),
            str(EXAMPLE.backup_dir),
            str(config.DEFAULT_CONFIG),
            "/etc/localtime",
        }, f"{name}: the server mounts its data, its backups, its config and the zone, nothing else"
        for spec in compose["services"].values():
            for v in spec.get("volumes", []):
                assert "keys" not in str(v), f"{name}: no key directory exists any more"


def test_host_commands_have_their_socket_and_the_proxy_is_trusted_alone():
    """Host commands reach the server over a Unix socket on a tmpfs of its account (S13.6), and
    the example trusts the proxy's own address, never a range anything else could share
    (S13.3)."""
    import ipaddress

    folder = str(config.DEFAULT_SOCKET.parent)
    for name, compose in COMPOSE.items():
        tmpfs = compose["services"]["moneykata"]["tmpfs"]
        assert f"{folder}:uid={SERVER_UID},gid={SERVER_UID},mode=0700" in tmpfs, name
    assert EXAMPLE.trusted_proxies
    subnet = ipaddress.ip_network(
        COMPOSE["compose.yaml"]["networks"]["default"]["ipam"]["config"][0]["subnet"]
    )
    for net in EXAMPLE.trusted_proxies:
        assert net.num_addresses == 1 and net.network_address in subnet, net
    assert (
        f"ipv4_address: {EXAMPLE.trusted_proxies[0].network_address}"
        in (INSTALL / "compose.yaml").read_text()
    )


def test_the_published_port_fits_each_mode():
    """Behind a reverse proxy the plain-HTTP listener is published on the host's loopback only;
    the proxy examples reach it by service name. The tls example serves the LAN itself."""
    port = config.DEFAULT_PORT
    assert COMPOSE["compose.yaml"]["services"]["moneykata"]["ports"] == [f"127.0.0.1:{port}:{port}"]
    assert COMPOSE["compose.tls.yaml"]["services"]["moneykata"]["ports"] == [f"{port}:{port}"]
    for example in (INSTALL / "proxy").iterdir():
        assert f"moneykata:{port}" in example.read_text(), example.name


def test_no_service_runs_as_root_and_the_key_commands_need_none():
    """`keys init` and `keys rotate` run as the image's own user: the keyring is in the data
    directory, which the server's account owns (S15.4.4)."""
    for name, compose in COMPOSE.items():
        services = compose["services"]
        assert set(services) == {"moneykata", "connector"}, name
        for service, spec in services.items():
            assert "user" not in spec, f"{name}: {service} must run as the image's user"
    text = (INSTALL / "compose.yaml").read_text()
    assert "docker compose run --rm moneykata keys init" in text
    assert "keys unlock" in text


def test_the_smoke_script_is_there_for_each_platform():
    """The release gate (S17.8.1): both images built for a platform and run once."""
    script = INSTALL / "smoke.sh"
    assert script.exists() and script.stat().st_mode & 0o111, (
        "web/install/smoke.sh must be executable"
    )
    text = script.read_text()
    assert "linux/arm64" in text and "keys unlock" in text
    # A new server's welcome, then the locked start after a restart (S15.4).
    assert "wait_for uninitialised" in text and "/ui/api/welcome/key" in text
    assert "wait_for locked" in text


def test_the_truenas_app_keeps_the_compose_files_promises():
    """install/compose.truenas.yaml (S17.8.3), which docs/DEPLOY.md shows to paste, is the tls
    example's server with the datasets for host paths and its configuration in
    MONEYKATA_CONFIG (S17.8), after a one-time step that gives the datasets to its account:
    the same lockdown, port, restart and logs, and the version being built; nothing typed in a
    shell."""
    truenas = yaml.safe_load((INSTALL / "compose.truenas.yaml").read_text())
    guide = (paths.ROOT / "docs" / "DEPLOY.md").read_text()
    blocks = re.findall(r"^```yaml\n(.*?)^```", guide, re.M | re.S)
    assert [yaml.safe_load(b) for b in blocks] == [truenas], "the guide shows the file as it is"
    app = truenas["services"]["moneykata"]
    tls = COMPOSE["compose.tls.yaml"]["services"]["moneykata"]
    differ = {"volumes", "environment", "depends_on"}
    assert {k: v for k, v in app.items() if k not in differ} == {
        k: v for k, v in tls.items() if k not in differ
    }
    want = {t: ro for t, (_, ro) in _mounts(tls).items() if t != str(config.DEFAULT_CONFIG)}
    assert {t: ro for t, (_, ro) in _mounts(app).items()} == want
    given = config.configured(None, app["environment"])
    assert (given.mode, given.port) == ("tls", 37373) and given.cert_names
    assert {str(given.data_dir), str(given.backup_dir)} <= set(_mounts(app))
    # The one-time step: root with CHOWN alone, no network, the datasets and nothing else, run
    # once before the server, which waits for it to succeed.
    step = truenas["services"]["permissions"]
    assert app["depends_on"] == {"permissions": {"condition": "service_completed_successfully"}}
    assert step["image"] == app["image"] and step["user"] == "0:0"
    assert step["entrypoint"] == [
        "chown",
        f"{SERVER_UID}:{SERVER_UID}",
        str(given.data_dir),
        str(given.backup_dir),
    ]
    assert step["cap_drop"] == ["ALL"] and step["cap_add"] == ["CHOWN"]
    assert step["network_mode"] == "none" and step["restart"] == "no" and step["read_only"]
    assert "no-new-privileges:true" in step["security_opt"]
    assert _mounts(step) == {t: m for t, m in _mounts(app).items() if t != "/etc/localtime"}
    version = paths.version()
    tags = re.findall(r"moneykata[:-](\d+\.\d+\.\d+)", guide)
    assert tags and set(tags) == {version}, f"the guide names {set(tags)}, the build {version}"


def test_the_workflows_pin_their_actions_and_the_register_lists_them():
    """S17.10.3: every action is pinned by a full commit, named in docs/dependencies.md with
    that commit, and a workflow's token can only read unless a job asks for more."""
    register = (paths.ROOT / "docs" / "dependencies.md").read_text()
    workflows = sorted((paths.ROOT / ".github" / "workflows").glob("*.yml"))
    assert workflows
    for wf in workflows:
        text = wf.read_text()
        assert yaml.safe_load(text)["permissions"] == {"contents": "read"}, wf.name
        for action, ref in re.findall(r"uses:\s*([\w.-]+/[\w.-]+)@(\S+)", text):
            assert re.fullmatch(r"[0-9a-f]{40}", ref), f"{wf.name}: {action}@{ref} is not a commit"
            assert f"| {action} |" in register and ref in register, (
                f"{action} isn't in the register"
            )

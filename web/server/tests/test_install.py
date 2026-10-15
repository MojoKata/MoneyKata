"""The image and the compose files keep what requirements S17.8, S15.4 and S13.6 promise:
the unprivileged user, the port, the mounts, the read-only key directory, the health check and
the refused start's restart policy. Checked on the files themselves, so a tag or a path can't
drift from the server's own constants."""

import re
import tomllib

import yaml

from moneykata import config, paths
from moneykata.dev import wheels
from moneykata.keys.cli import SERVER_UID

INSTALL = paths.WEB / "install"
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
    assert f"-m 0755 {EXAMPLE.key_file.parent}" in DOCKERFILE
    assert EXAMPLE.mode == "proxy" and EXAMPLE.port == config.DEFAULT_PORT


def test_every_compose_service_runs_the_image_of_this_version():
    tag = f"moneykata:{paths.version()}"
    for name, compose in COMPOSE.items():
        for service, spec in compose["services"].items():
            assert spec["image"] == tag, f"{name}: {service} runs {spec['image']}, not {tag}"


def test_the_server_service_is_locked_down_and_its_key_directory_read_only():
    key_dir = str(EXAMPLE.key_file.parent)
    for name, compose in COMPOSE.items():
        service = compose["services"]["moneykata"]
        assert service["read_only"] is True, name
        assert service["cap_drop"] == ["ALL"], name
        assert "no-new-privileges:true" in service["security_opt"], name
        assert "/tmp" in service["tmpfs"], name
        # A refused start (exit 78) is retried a few times, never in a loop (S13.6).
        assert service["restart"] == "on-failure:3", name
        mounts = _mounts(service)
        assert mounts[key_dir][1], f"{name}: the key directory must be mounted read only"
        assert mounts[str(config.DEFAULT_CONFIG)][1], f"{name}: moneykata.toml must be read only"
        assert not mounts[str(EXAMPLE.data_dir)][1] and not mounts[str(EXAMPLE.backup_dir)][1]
        # The key directory is never backed up with the data: it is its own host directory.
        assert mounts[key_dir][0] not in (
            mounts[str(EXAMPLE.data_dir)][0],
            mounts[str(EXAMPLE.backup_dir)][0],
        )


def test_the_published_port_fits_each_mode():
    """Behind a reverse proxy the plain-HTTP listener is published on the host's loopback only;
    the proxy examples reach it by service name. The tls example serves the LAN itself."""
    port = config.DEFAULT_PORT
    assert COMPOSE["compose.yaml"]["services"]["moneykata"]["ports"] == [f"127.0.0.1:{port}:{port}"]
    assert COMPOSE["compose.tls.yaml"]["services"]["moneykata"]["ports"] == [f"{port}:{port}"]
    for example in (INSTALL / "proxy").iterdir():
        assert f"moneykata:{port}" in example.read_text(), example.name


def test_only_the_key_commands_mount_the_key_directory_writable():
    """`keys init` and `keys rotate` run as root in one-off containers and write the key
    directory; only `rotate` writes moneykata.toml (S15.4.6)."""
    key_dir = str(EXAMPLE.key_file.parent)
    toml = str(config.DEFAULT_CONFIG)
    for name, compose in COMPOSE.items():
        services = compose["services"]
        for service in ("keys-init", "keys-rotate"):
            spec = services[service]
            assert spec["user"] == "0:0", f"{name}: {service}"
            assert spec["profiles"] == ["keys"], f"{name}: {service}"
            assert spec["command"] == ["keys", service.removeprefix("keys-")], f"{name}: {service}"
            assert not _mounts(spec)[key_dir][1], f"{name}: {service} needs the key directory"
        assert _mounts(services["keys-init"])[toml][1], f"{name}: keys-init keeps the config ro"
        assert not _mounts(services["keys-rotate"])[toml][1], f"{name}: keys-rotate writes it"
        for service, spec in services.items():
            if service not in ("keys-init", "keys-rotate"):
                assert "user" not in spec, f"{name}: {service} must run as the image's user"

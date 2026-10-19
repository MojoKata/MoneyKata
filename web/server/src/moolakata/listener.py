"""The listener (requirements S13.3, S13.6): plain HTTP behind a proxy, or its own HTTPS with
HTTP/2; and stopping cleanly on SIGTERM."""

import asyncio
import datetime as dt
import errno
import ipaddress
import logging
import os
import signal
import ssl
from collections.abc import Awaitable, Callable
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from hypercorn.asyncio import serve
from hypercorn.config import Config as HypercornConfig

from .config import Config, RefuseStart

log = logging.getLogger("moolakata.listener")

GRACE_SECONDS = 5
HEADER_LIMIT = 16 * 1024


def self_signed(directory: Path, names: list[str]) -> tuple[Path, Path]:
    """Make a self-signed certificate on first start and keep it in the data directory. One
    that no longer covers every name is made again."""
    cert_path, key_path = directory / "self-signed.crt", directory / "self-signed.key"
    if cert_path.exists() and key_path.exists() and set(names) <= _covers(cert_path):
        return cert_path, key_path
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0])])
    alt: list[x509.GeneralName] = []
    for n in names:
        try:
            alt.append(x509.IPAddress(ipaddress.ip_address(n)))
        except ValueError:
            alt.append(x509.DNSName(n))
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(alt), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


def _covers(cert_path: Path) -> set[str]:
    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        alt = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except ValueError, x509.ExtensionNotFound:
        return set()
    return {str(n.value) for n in alt}


def hypercorn_config(config: Config) -> HypercornConfig:
    hc = HypercornConfig()
    hc.bind = [
        f"[{config.host}]:{config.port}" if ":" in config.host else f"{config.host}:{config.port}"
    ]
    hc.graceful_timeout = GRACE_SECONDS
    # Over HTTP/2 a browser sends everything on one connection, the live stream included; the
    # default cap of 1,000 requests a connection would end it every few minutes of use and
    # strand the requests in flight.
    hc.keep_alive_max_requests = 1_000_000
    hc.h11_max_incomplete_size = HEADER_LIMIT
    hc.h2_max_header_list_size = HEADER_LIMIT
    hc.accesslog = None
    hc.errorlog = logging.getLogger("hypercorn.error")
    hc.include_server_header = False
    if config.mode == "tls":
        if config.tls_cert and config.tls_key:
            cert, key = config.tls_cert, config.tls_key
        else:
            names = ["localhost", "127.0.0.1"] if config.dev else [config.name, "localhost"]
            names = list(dict.fromkeys([*config.cert_names, *names]))
            cert, key = self_signed(config.tls_dir, names)
        for p in (cert, key):
            if not p.is_file():
                raise RefuseStart(f"TLS file {p} does not exist")
        try:
            ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ctx.load_cert_chain(cert, key)
        except (ssl.SSLError, OSError) as e:
            raise RefuseStart(f"the TLS certificate or key cannot be loaded: {e}") from None
        hc.certfile = str(cert)
        hc.keyfile = str(key)
        hc.alpn_protocols = ["h2", "http/1.1"]
    return hc


async def run(app, config: Config, on_stop: Callable[[], Awaitable[None]], host_app=None) -> None:
    """Serve until SIGTERM or SIGINT. The first signal ends the event streams (on_stop) and lets
    requests in flight finish for up to 5 seconds; a second one stops at once. The host
    commands' app, when given, is served on its Unix socket beside the listener (host.py)."""
    from . import host

    hc = hypercorn_config(config)
    host_hc = host.hypercorn_config(config) if host_app is not None else None
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    first: list[float] = []

    def on_signal(signum: int) -> None:
        if stopping.is_set():
            # A launcher (uv run, a terminal's process group) can deliver one Ctrl-C twice;
            # a repeat within a second is the same request.
            if loop.time() - first[0] > 1.0:
                log.warning("second signal: stopping now")
                os._exit(1)
            return
        first.append(loop.time())
        log.info("stopping (%s)", signal.Signals(signum).name)
        stopping.set()

    for s in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(s, on_signal, s)

    async def trigger() -> None:
        await stopping.wait()
        await on_stop()

    try:
        if host_hc is None:
            await serve(app, hc, shutdown_trigger=trigger)
        else:
            await asyncio.gather(
                serve(app, hc, shutdown_trigger=trigger),
                serve(host_app, host_hc, shutdown_trigger=stopping.wait),
            )
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            raise RefuseStart(f"port {config.port} is already in use") from None
        if e.errno == errno.EACCES:
            raise RefuseStart(f"this account may not listen on port {config.port}") from None
        raise

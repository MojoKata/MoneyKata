"""Emails (requirements S10.1.9): plain text. Until SMTP is set up (and always in dev mode)
each one is written to the mail folder as an .eml file; dev mode also prints its links.

With SMTP set up (S16.2), an email is written to the outbox and the mail task sends it at
once, in the background, so a request never waits on the mail server. What can't be sent
stays in the outbox and is tried again every five minutes; Settings › Email shows the queue
and the last error. The SMTP host is one the egress guard allows, by name (S13.5).

Links are built from Settings › General's public URL, never from the request (S16.1). A
token rides in the link's fragment (#…), which browsers send to no server and no Referer.
"""

import datetime as dt
import email
import email.policy
import logging
import os
import secrets
import smtplib
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid, parseaddr
from pathlib import Path

from sqlalchemy.orm import Session

from . import settings
from .config import Config
from .errors import refuse

log = logging.getLogger("moneykata.mail")


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str


def base_url(s: Session, config: Config) -> str:
    url = settings.get(s, "publicUrl")
    if url:
        return url
    if config.dev:
        return f"https://localhost:{config.port}"
    raise refuse(
        "publicUrl",
        "public-url-needed",
        "Set the server's public URL in Settings › General first: links in emails "
        "are built from it.",
    )


def link(s: Session, config: Config, path: str, token: str | None = None) -> str:
    url = base_url(s, config) + path
    return f"{url}#{token}" if token else url


SMTP_TIMEOUT = 20
SMTP_SECRET = ("Setting", "smtp", "password")


@dataclass(frozen=True)
class Smtp:
    host: str
    port: int
    security: str  # starttls, tls or none
    username: str | None
    password: str | None
    sender: str


def smtp_settings(s: Session, secrets_key: bytes) -> Smtp | None:
    """SMTP as Settings › Email has it, or None while no host is set."""
    from .store.repos import secrets as secret_repo

    host = settings.get(s, "smtpHost")
    if not host:
        return None
    username = settings.get(s, "smtpUsername")
    sender = settings.get(s, "smtpFrom")
    if not sender:
        household = settings.get(s, "householdName")
        address = username if username and "@" in username else f"moneykata@{host}"
        sender = f"MoneyKata ({household}) <{address}>"
    return Smtp(
        host=host,
        port=settings.get(s, "smtpPort"),
        security=settings.get(s, "smtpSecurity"),
        username=username,
        password=secret_repo.use(s, secrets_key, *SMTP_SECRET),
        sender=sender,
    )


def deliver(smtp: Smtp, msg: EmailMessage, guard) -> None:
    """Hand one message to the SMTP server, through the egress guard."""
    guard.check(smtp.host, smtp.port)
    context = ssl.create_default_context()
    if smtp.security == "tls":
        conn = smtplib.SMTP_SSL(smtp.host, smtp.port, timeout=SMTP_TIMEOUT, context=context)
    else:
        conn = smtplib.SMTP(smtp.host, smtp.port, timeout=SMTP_TIMEOUT)
    with conn:
        conn.ehlo()
        if smtp.security == "starttls":
            conn.starttls(context=context)
            conn.ehlo()
        if smtp.username:
            conn.login(smtp.username, smtp.password or "")
        del msg["From"]
        msg["From"] = smtp.sender
        conn.send_message(msg, from_addr=parseaddr(smtp.sender)[1])


def describe(e: Exception) -> str:
    """What went wrong, in words an admin can act on, never a password."""
    if isinstance(e, smtplib.SMTPAuthenticationError):
        return "the SMTP server refused the username or password"
    if isinstance(e, smtplib.SMTPNotSupportedError):
        return "the SMTP server does not offer STARTTLS: try TLS or None"
    if isinstance(e, smtplib.SMTPRecipientsRefused):
        return "the SMTP server refused the recipient's address"
    if isinstance(e, smtplib.SMTPSenderRefused):
        return "the SMTP server refused the From address"
    if isinstance(e, ssl.SSLError):
        return f"TLS failed: {e.reason or e}"
    if isinstance(e, TimeoutError | ConnectionError | OSError):
        return f"could not reach the SMTP server: {e}"
    return str(e) or type(e).__name__


class Mailer:
    def __init__(self, config: Config) -> None:
        self.config = config
        # Set once the background tasks exist: starts the mail task for a queued email.
        self.notify: Callable[[], None] = lambda: None

    def send(self, s: Session, email: Email) -> None:
        msg = EmailMessage()
        household = settings.get(s, "householdName")
        msg["From"] = f"MoneyKata ({household}) <moneykata@localhost>"
        msg["To"] = email.to
        msg["Subject"] = email.subject
        msg["Date"] = format_datetime(dt.datetime.now(dt.UTC))
        msg["Message-ID"] = make_msgid(domain="moneykata.local")
        msg.set_content(email.body)
        if not self.config.dev and settings.get(s, "smtpHost"):
            self._file(self.config.outbox_dir, msg)
            self.notify()
            return
        self._write(msg)

    def _file(self, folder: Path, msg: EmailMessage) -> Path:
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S-%f")
        path = folder / f"{stamp}-{secrets.token_hex(4)}.eml"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(bytes(msg))
        return path

    def _write(self, msg: EmailMessage) -> None:
        self._file(self.config.mail_dir, msg)
        if self.config.dev:
            links = [w for w in msg.get_content().split() if w.startswith("https://")]
            log.info("dev mail to %s: %s %s", msg["To"], msg["Subject"], " ".join(links))
        else:
            log.info("an email was written to the mail folder (SMTP is not set up)")

    def waiting(self) -> list[Path]:
        folder = self.config.outbox_dir
        return sorted(folder.glob("*.eml")) if folder.is_dir() else []

    def send_waiting(self, smtp: Smtp | None, guard, stop=None) -> int:
        """The mail task: send what the outbox holds, oldest first. The first failure stops
        the run, which records it, and the rest wait for the next."""
        if smtp is None:
            return 0
        sent = 0
        for path in self.waiting():
            if stop is not None and stop.is_set():
                break
            msg = email.message_from_bytes(
                path.read_bytes(), _class=EmailMessage, policy=email.policy.default
            )
            try:
                deliver(smtp, msg, guard)
            except smtplib.SMTPRecipientsRefused:
                # This address will never take it: set it aside rather than block the rest.
                path.rename(path.with_suffix(".refused"))
                log.warning("the SMTP server refused an email's recipient; it was set aside")
                continue
            except Exception as e:
                raise RuntimeError(describe(e)) from None
            path.unlink()
            sent += 1
        if sent:
            log.info("sent %d email%s", sent, "" if sent == 1 else "s")
        return sent

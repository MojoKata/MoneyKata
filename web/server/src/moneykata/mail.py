"""Emails (requirements S10.1.9): plain text. Until SMTP is set up (and always in dev mode)
each one is written to the mail folder as an .eml file; dev mode also prints its links.

Links are built from Settings › General's public URL, never from the request (S16.1). A
token rides in the link's fragment (#…), which browsers send to no server and no Referer.
"""

import datetime as dt
import logging
import os
import secrets
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid

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


class Mailer:
    def __init__(self, config: Config) -> None:
        self.config = config

    def send(self, s: Session, email: Email) -> None:
        msg = EmailMessage()
        household = settings.get(s, "householdName")
        msg["From"] = f"MoneyKata ({household}) <moneykata@localhost>"
        msg["To"] = email.to
        msg["Subject"] = email.subject
        msg["Date"] = format_datetime(dt.datetime.now(dt.UTC))
        msg["Message-ID"] = make_msgid(domain="moneykata.local")
        msg.set_content(email.body)
        self._write(msg)

    def _write(self, msg: EmailMessage) -> None:
        folder = self.config.mail_dir
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S-%f")
        path = folder / f"{stamp}-{secrets.token_hex(4)}.eml"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(bytes(msg))
        if self.config.dev:
            links = [w for w in msg.get_content().split() if w.startswith("https://")]
            log.info("dev mail to %s: %s %s", msg["To"], msg["Subject"], " ".join(links))
        else:
            log.info("an email was written to the mail folder (SMTP is not set up)")

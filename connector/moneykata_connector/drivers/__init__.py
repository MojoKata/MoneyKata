"""Drivers (requirements S18.1.1, S18.8): one per institution or method. Each declares the
hosts it talks to, the credential fields it needs and how often it runs, and turns what its
institution offers into files MoneyKata already imports, posted for one account."""

from dataclasses import dataclass, field


@dataclass
class Account:
    """An account whose sync names this Connection, as MoneyKata reports it."""

    id: str
    sync_account: str | None  # "Individual ••4417": the institution account's name and last 4
    formats: list[str]

    @property
    def last4(self) -> str | None:
        s = (self.sync_account or "").strip()
        return s[-4:] if s[-4:].isdigit() else None


@dataclass
class File:
    account_id: str
    name: str
    data: bytes
    fmt: str  # ofx, csv or statement


@dataclass
class Result:
    state: str = "ok"  # ok, needs-sign-in, failing
    message: str | None = None
    found: list[dict] = field(default_factory=list)  # [{name, last4}] the driver found
    files: list[File] = field(default_factory=list)
    sign_in: str | None = None  # an address the owner must open (S18.7.1)
    credentials: dict | None = None  # changed credentials to keep (a refreshed token)


class Driver:
    name = "driver"
    hosts: tuple[str, ...] = ()  # the only hosts it may reach
    needs: tuple[str, ...] = ()  # credential fields
    interval = 24 * 3600  # seconds between runs

    def hosts_for(self, settings: dict) -> tuple[str, ...]:
        """The hosts this Connection reaches: the declared ones, or one its owner named."""
        return self.hosts

    def sign_in(self, settings: dict) -> str | None:
        """An address the owner must sign in at before credentials exist (S18.7.1)."""
        return None

    def run(
        self, settings: dict, credentials: dict | None, accounts: list[Account], http
    ) -> Result:
        raise NotImplementedError


def registry() -> dict[str, Driver]:
    from .folder import Folder
    from .ofx_direct import OfxDirect
    from .schwab import Schwab

    return {d.name: d for d in (Folder(), OfxDirect(), Schwab())}

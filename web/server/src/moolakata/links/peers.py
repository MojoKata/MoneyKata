"""The links this server has (requirements S11.1, S11.7)."""

from urllib.parse import urlsplit

from sqlalchemy import false, select

from ..store.entities.links import Link


def hosts(s) -> list[str]:
    """Linked servers' hosts, for the egress guard: reachable on the LAN or an overlay, never on
    loopback, link-local or metadata addresses, since another server supplied them (S13.5); a
    request is reached only once its admin approves it."""
    out = set()
    for addr in s.scalars(
        select(Link.address).where(
            Link.deleted == false(), Link.state.in_(("pending", "active", "paused"))
        )
    ):
        host = urlsplit(addr or "").hostname
        if host:
            out.add(host.lower())
    return sorted(out)

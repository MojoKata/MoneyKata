"""The links this server has (requirements S11.1, S11.7)."""

from urllib.parse import urlsplit

from sqlalchemy import false, select

from ..store.entities.links import Link


def hosts(s) -> list[str]:
    """Linked servers' hosts, for the egress guard: named by an admin, so reachable on the LAN."""
    out = set()
    for addr in s.scalars(
        select(Link.address).where(
            Link.deleted == false(), Link.state.in_(("requested", "pending", "active", "paused"))
        )
    ):
        host = urlsplit(addr or "").hostname
        if host:
            out.add(host.lower())
    return sorted(out)

"""Dev mode's linked server (requirements S17.7): griffin-parents, linked and active, with its
two users, so linked people can be shared with. Its address is never reached: dev mode with
stubs makes no outside calls."""

import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .. import clock, ids
from ..links import keys
from ..links.manage import apply_directory
from ..store.entities.links import Link


def seed_links(s, people: dict) -> None:
    peer = keys.raw_public(Ed25519PrivateKey.generate().public_key())
    link = Link(
        id=ids.new_id("Link"),
        state="active",
        role="inviter",
        peerName="griffin-parents",
        householdName="Margaret & Tom",
        householdAvatar=json.dumps({"kind": "initials", "initials": "MT", "color": "#7a4b9c"}),
        address="https://money.parents.ts.net",
        peerKey=keys.b64(peer),
        approvedById=people["admin"].id if "admin" in people else None,
        approvedAt=clock.now(),
        lastOkAt=clock.now(),
        peerVersion="0.1.0",
    )
    s.add(link)
    s.flush()
    apply_directory(
        s,
        link,
        {
            "household": {"serverName": "griffin-parents", "name": "Margaret & Tom"},
            "users": [
                {
                    "id": "User_01m4parentsmargaret00000a",
                    "username": "margaret",
                    "displayName": "Margaret Griffin",
                    "email": "margaret@parents.home",
                },
                {
                    "id": "User_01m4parentstom0000000000b",
                    "username": "tom",
                    "displayName": "Tom Griffin",
                    "email": "tom@parents.home",
                },
            ],
        },
    )

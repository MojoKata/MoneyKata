"""Opening a credential sealed in the owner's browser (docs/connector-protocol.md §4.3): the
ephemeral X25519 key, a nonce and AES-256-GCM, under HKDF-SHA256 over the exchange with the
sealing key, salted by the Connection's id. The sealing key comes from the vault, so this runs
only while the connector is unlocked."""

import json

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .keys import unb64

LABEL = b"moneykata connector credential"


def open_box(box: str, sealing: X25519PrivateKey | bytes, connection_id: str) -> dict:
    if isinstance(sealing, bytes):
        sealing = X25519PrivateKey.from_private_bytes(sealing)
    raw = unb64(box)
    if len(raw) < 32 + 12 + 16:
        raise ValueError("not a sealed box")
    shared = sealing.exchange(X25519PublicKey.from_public_bytes(raw[:32]))
    key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=connection_id.encode(), info=LABEL
    ).derive(shared)
    plain = AESGCM(key).decrypt(raw[32:44], raw[44:], None)
    out = json.loads(plain)
    if not isinstance(out, dict):
        raise ValueError("a credential is a JSON object")
    return out

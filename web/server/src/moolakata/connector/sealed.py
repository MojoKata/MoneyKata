"""Credentials sealed for the connector (requirements S18.7.1, docs/connector-protocol.md
§4.3): an X25519 sealed box the browser makes with WebCrypto (`web/ui/app/sealed.js`) and only
the connector's sealing key opens. MoolaKata keeps the box as it is and never has the key; this
module is the same construction in Python, for the connector's side and the tests.

    box = ephemeral public key (32) ‖ nonce (12) ‖ AES-256-GCM ciphertext, base64url
    key = HKDF-SHA256(X25519(ephemeral, sealing key), salt = the Connection's id,
                      info = "moolakata connector credential")
"""

import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ..links.keys import b64, unb64

LABEL = b"moolakata connector credential"


def _key(shared: bytes, salt: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=LABEL).derive(shared)


def seal(plaintext: bytes, sealing_public: bytes, connection_id: str) -> str:
    once = X25519PrivateKey.generate()
    shared = once.exchange(X25519PublicKey.from_public_bytes(sealing_public))
    nonce = os.urandom(12)
    sealed = AESGCM(_key(shared, connection_id.encode())).encrypt(nonce, plaintext, None)
    public = once.public_key().public_bytes_raw()
    return b64(public + nonce + sealed)


def open_box(box: str, sealing_private: X25519PrivateKey, connection_id: str) -> bytes:
    raw = unb64(box)
    if len(raw) < 32 + 12 + 16:
        raise ValueError("not a sealed box")
    public, nonce, sealed = raw[:32], raw[32:44], raw[44:]
    shared = sealing_private.exchange(X25519PublicKey.from_public_bytes(public))
    return AESGCM(_key(shared, connection_id.encode())).decrypt(nonce, sealed, None)


def looks_sealed(box: str) -> bool:
    try:
        return len(unb64(box)) >= 32 + 12 + 16
    except ValueError:
        return False

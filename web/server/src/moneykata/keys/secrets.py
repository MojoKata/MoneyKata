"""Secrets (requirements §17.4, §18.3.3): price-source keys, the bitcoin node's credentials,
the SMTP password, the link key. Each is encrypted on its own with AES-256-GCM under a random
data key of its own, with associated data naming the record and field, so a ciphertext copied
onto another record fails to decrypt. The secret's data key is wrapped under the secrets key.
"""

import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SecretError(ValueError):
    pass


@dataclass(frozen=True)
class Sealed:
    ciphertext: bytes
    nonce: bytes
    wrappedKey: bytes


def _aad(record_type: str, record_id: str, field: str) -> bytes:
    return "\x1f".join(("moneykata secret", record_type, record_id, field)).encode()


def seal(secrets_key: bytes, value: str, record_type: str, record_id: str, field: str) -> Sealed:
    dek = AESGCM.generate_key(256)
    aad = _aad(record_type, record_id, field)
    nonce = os.urandom(12)
    ciphertext = AESGCM(dek).encrypt(nonce, value.encode(), aad)
    wrap_nonce = os.urandom(12)
    wrapped = wrap_nonce + AESGCM(secrets_key).encrypt(wrap_nonce, dek, aad)
    return Sealed(ciphertext, nonce, wrapped)


def open_sealed(
    secrets_key: bytes, sealed: Sealed, record_type: str, record_id: str, field: str
) -> str:
    """Decrypt a secret for one use. Any tampering, a wrong key, or a ciphertext moved to
    another record or field fails instead of giving a wrong value."""
    aad = _aad(record_type, record_id, field)
    try:
        dek = AESGCM(secrets_key).decrypt(sealed.wrappedKey[:12], sealed.wrappedKey[12:], aad)
        return AESGCM(dek).decrypt(sealed.nonce, sealed.ciphertext, aad).decode()
    except InvalidTag:
        raise SecretError(f"the {field} of {record_id} cannot be decrypted") from None


def rewrap(
    old_key: bytes, new_key: bytes, sealed: Sealed, record_type: str, record_id: str, field: str
) -> Sealed:
    """Re-encrypting (§18.7.2): a fresh data key and nonce under the new secrets key."""
    return seal(
        new_key,
        open_sealed(old_key, sealed, record_type, record_id, field),
        record_type,
        record_id,
        field,
    )

from __future__ import annotations

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def derive_wrap_key_and_nonce(
    shared_secret: bytes,
    salt_wrap: bytes,
    info: bytes,
) -> tuple[bytes, bytes]:
    """
    Output:
    - wrap_key: 32 bytes
    - wrap_nonce: 12 bytes
    """
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=44,  # 32 + 12
        salt=salt_wrap,
        info=info,
    )
    out = hkdf.derive(shared_secret)
    return out[:32], out[32:]
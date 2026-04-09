from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric import ed25519


def sign_bytes(private_key: ed25519.Ed25519PrivateKey, data: bytes) -> bytes:
    return private_key.sign(data)


def verify_bytes(public_key: ed25519.Ed25519PublicKey, data: bytes, signature: bytes) -> bool:
    try:
        public_key.verify(signature, data)
        return True
    except Exception:
        return False
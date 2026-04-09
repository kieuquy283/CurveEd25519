from __future__ import annotations

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305


def encrypt_aead(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    cipher = ChaCha20Poly1305(key)
    return cipher.encrypt(nonce, plaintext, aad)


def decrypt_aead(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    cipher = ChaCha20Poly1305(key)
    return cipher.decrypt(nonce, ciphertext, aad)
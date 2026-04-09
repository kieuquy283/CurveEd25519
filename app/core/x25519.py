# app/core/x25519.py

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Union

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)


BytesLike = Union[bytes, bytearray]


@dataclass(frozen=True)
class X25519KeyPair:
    """
    Container cho một cặp khóa X25519 ở dạng base64 để:
    - dễ lưu JSON
    - dễ truyền giữa service/storage/UI
    """
    private_key_b64: str
    public_key_b64: str

    def to_dict(self) -> dict:
        return {
            "private_key": self.private_key_b64,
            "public_key": self.public_key_b64,
        }


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _b64decode(data_b64: str) -> bytes:
    try:
        return base64.b64decode(data_b64.encode("utf-8"), validate=True)
    except Exception as exc:
        raise ValueError("Invalid base64 key data.") from exc


def _ensure_32_bytes(raw: bytes, field_name: str) -> None:
    if len(raw) != 32:
        raise ValueError(f"{field_name} must be exactly 32 bytes for X25519.")


def generate_private_key() -> X25519PrivateKey:
    """
    Sinh private key object X25519.
    """
    return X25519PrivateKey.generate()


def derive_public_key(private_key: X25519PrivateKey) -> X25519PublicKey:
    """
    Lấy public key từ private key object.
    """
    return private_key.public_key()


def private_key_to_bytes(private_key: X25519PrivateKey) -> bytes:
    """
    Export private key về raw 32 bytes.
    """
    return private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def public_key_to_bytes(public_key: X25519PublicKey) -> bytes:
    """
    Export public key về raw 32 bytes.
    """
    return public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def private_key_to_b64(private_key: X25519PrivateKey) -> str:
    return _b64encode(private_key_to_bytes(private_key))


def public_key_to_b64(public_key: X25519PublicKey) -> str:
    return _b64encode(public_key_to_bytes(public_key))


def load_private_key_from_bytes(raw_private_key: BytesLike) -> X25519PrivateKey:
    """
    Load private key object từ raw 32 bytes.
    """
    raw = bytes(raw_private_key)
    _ensure_32_bytes(raw, "Private key")
    return X25519PrivateKey.from_private_bytes(raw)


def load_public_key_from_bytes(raw_public_key: BytesLike) -> X25519PublicKey:
    """
    Load public key object từ raw 32 bytes.
    """
    raw = bytes(raw_public_key)
    _ensure_32_bytes(raw, "Public key")
    return X25519PublicKey.from_public_bytes(raw)


def load_private_key_from_b64(private_key_b64: str) -> X25519PrivateKey:
    raw = _b64decode(private_key_b64)
    return load_private_key_from_bytes(raw)


def load_public_key_from_b64(public_key_b64: str) -> X25519PublicKey:
    raw = _b64decode(public_key_b64)
    return load_public_key_from_bytes(raw)


def generate_keypair() -> X25519KeyPair:
    """
    Sinh cặp khóa X25519 và trả về ở dạng base64.
    Đây là hàm phù hợp nhất để gọi từ key_service / profile creation.
    """
    private_key = generate_private_key()
    public_key = derive_public_key(private_key)

    return X25519KeyPair(
        private_key_b64=private_key_to_b64(private_key),
        public_key_b64=public_key_to_b64(public_key),
    )


def generate_ephemeral_keypair() -> X25519KeyPair:
    """
    Alias rõ nghĩa cho encrypt flow.
    Mỗi message nên dùng 1 ephemeral key mới.
    """
    return generate_keypair()


def derive_shared_secret(
    private_key: X25519PrivateKey,
    peer_public_key: X25519PublicKey,
) -> bytes:
    """
    Derive shared secret từ private key của mình và public key của peer.
    Kết quả là 32 bytes raw shared secret.
    """
    return private_key.exchange(peer_public_key)


def derive_shared_secret_from_b64(
    private_key_b64: str,
    peer_public_key_b64: str,
) -> bytes:
    """
    Dùng khi keys đang nằm trong profile/contact JSON.
    """
    private_key = load_private_key_from_b64(private_key_b64)
    peer_public_key = load_public_key_from_b64(peer_public_key_b64)
    return derive_shared_secret(private_key, peer_public_key)


def derive_shared_secret_b64(
    private_key_b64: str,
    peer_public_key_b64: str,
) -> str:
    """
    Bản base64 của shared secret.
    Chỉ nên dùng cho debug/demo, không nên lưu dài hạn.
    """
    shared_secret = derive_shared_secret_from_b64(
        private_key_b64=private_key_b64,
        peer_public_key_b64=peer_public_key_b64,
    )
    return _b64encode(shared_secret)


def key_fingerprint_from_public_key_b64(public_key_b64: str, length: int = 16) -> str:
    """
    Tạo fingerprint ngắn từ public key để hiển thị trong UI/contact list.
    Mặc định lấy 16 hex chars đầu của SHA-256.
    """
    raw_public_key = _b64decode(public_key_b64)
    digest = hashlib.sha256(raw_public_key).hexdigest()
    return digest[:length]


def validate_public_key_b64(public_key_b64: str) -> bool:
    """
    Check nhanh public key base64 có hợp lệ không.
    """
    try:
        load_public_key_from_b64(public_key_b64)
        return True
    except Exception:
        return False


def validate_private_key_b64(private_key_b64: str) -> bool:
    """
    Check nhanh private key base64 có hợp lệ không.
    """
    try:
        load_private_key_from_b64(private_key_b64)
        return True
    except Exception:
        return False


def export_public_key_record(public_key_b64: str) -> dict:
    """
    Tạo record gọn để lưu contact/public card.
    """
    if not validate_public_key_b64(public_key_b64):
        raise ValueError("Invalid X25519 public key.")

    return {
        "algorithm": "X25519",
        "public_key": public_key_b64,
        "fingerprint": key_fingerprint_from_public_key_b64(public_key_b64),
    }


def export_full_keypair_record(keypair: X25519KeyPair) -> dict:
    """
    Tạo record đầy đủ để lưu profile nội bộ.
    """
    if not validate_private_key_b64(keypair.private_key_b64):
        raise ValueError("Invalid X25519 private key.")
    if not validate_public_key_b64(keypair.public_key_b64):
        raise ValueError("Invalid X25519 public key.")

    return {
        "algorithm": "X25519",
        "private_key": keypair.private_key_b64,
        "public_key": keypair.public_key_b64,
        "fingerprint": key_fingerprint_from_public_key_b64(keypair.public_key_b64),
    }
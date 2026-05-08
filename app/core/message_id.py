from __future__ import annotations

import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final


DEFAULT_MESSAGE_ID_BYTES: Final[int] = 16

# 128-bit hex => 32 hex chars
HEX_MESSAGE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[0-9a-f]+$"
)


class MessageIDError(Exception):
    """Raised when message ID operations fail."""


@dataclass(frozen=True, slots=True)
class MessageIDInfo:
    """
    Metadata mô tả message ID.
    """

    value: str
    created_at: str
    scheme: str


def utc_now_iso() -> str:
    """
    UTC ISO8601 timestamp.

    Example:
        2026-05-07T12:30:00Z
    """
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def generate_message_id_hex(num_bytes: int = DEFAULT_MESSAGE_ID_BYTES) -> str:
    """
    Sinh message ID dạng random hex.

    Default:
        16 bytes -> 128-bit ID

    Example:
        '4af8e2c0d9ab11223344ffeedd998877'
    """
    if not isinstance(num_bytes, int):
        raise MessageIDError("num_bytes must be an integer.")

    if num_bytes <= 0:
        raise MessageIDError("num_bytes must be > 0.")

    return secrets.token_hex(num_bytes)


def generate_message_id_uuid() -> str:
    """
    Sinh UUIDv4 message ID.

    Example:
        '550e8400-e29b-41d4-a716-446655440000'
    """
    return str(uuid.uuid4())

def generate_message_id() -> str:
    return generate_message_id_uuid()


def build_message_id_info_hex(
    num_bytes: int = DEFAULT_MESSAGE_ID_BYTES,
) -> MessageIDInfo:
    """
    Sinh message ID kèm metadata.

    Useful cho:
    - logging
    - replay protection
    - debugging
    """
    return MessageIDInfo(
        value=generate_message_id_hex(num_bytes),
        created_at=utc_now_iso(),
        scheme="hex",
    )


def build_message_id_info_uuid() -> MessageIDInfo:
    """
    Sinh UUID message ID kèm metadata.
    """
    return MessageIDInfo(
        value=generate_message_id_uuid(),
        created_at=utc_now_iso(),
        scheme="uuid4",
    )


def validate_message_id(
    message_id: str,
    *,
    min_length: int = 16,
    max_length: int = 128,
) -> bool:
    """
    Validate cơ bản cho message ID.

    Checks:
    - type
    - empty
    - length
    - printable
    """
    if not isinstance(message_id, str):
        return False

    message_id = message_id.strip()

    if not message_id:
        return False

    if len(message_id) < min_length:
        return False

    if len(message_id) > max_length:
        return False

    return message_id.isprintable()


def validate_hex_message_id(
    message_id: str,
    *,
    expected_num_bytes: int = DEFAULT_MESSAGE_ID_BYTES,
) -> bool:
    """
    Validate strict hex message ID.

    Default:
        16 bytes => 32 hex chars
    """
    if not validate_message_id(message_id):
        return False

    expected_len = expected_num_bytes * 2

    if len(message_id) != expected_len:
        return False

    return bool(HEX_MESSAGE_ID_PATTERN.fullmatch(message_id))


def validate_uuid_message_id(message_id: str) -> bool:
    """
    Validate UUIDv4 message ID.
    """
    if not validate_message_id(message_id):
        return False

    try:
        parsed = uuid.UUID(message_id, version=4)
    except Exception:
        return False

    return str(parsed) == message_id


def normalize_message_id(message_id: str) -> str:
    """
    Normalize message ID để:
    - storage
    - replay cache
    - comparison
    """
    if not isinstance(message_id, str):
        raise MessageIDError("message_id must be a string.")

    normalized = message_id.strip().lower()

    if not normalized:
        raise MessageIDError("message_id cannot be empty.")

    return normalized


def ensure_valid_message_id(message_id: str) -> str:
    """
    Validate + normalize message ID.

    Raise exception nếu invalid.
    """
    normalized = normalize_message_id(message_id)

    if not validate_message_id(normalized):
        raise MessageIDError("Invalid message ID.")

    return normalized


__all__ = [
    "DEFAULT_MESSAGE_ID_BYTES",
    "MessageIDError",
    "MessageIDInfo",
    "utc_now_iso",
    "generate_message_id_hex",
    "generate_message_id_uuid",
    "generate_message_id",
    "build_message_id_info_hex",
    "build_message_id_info_uuid",
    "validate_message_id",
    "validate_hex_message_id",
    "validate_uuid_message_id",
    "normalize_message_id",
    "ensure_valid_message_id",
]
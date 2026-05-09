from __future__ import annotations

from enum import Enum
from typing import Final, Set


# =========================================================
# Packet Types
# =========================================================

class PacketType(str, Enum):
    """
    Transport-level packet types.

    These packet types are exchanged
    over websocket transport.
    """

    # =====================================================
    # Messaging
    # =====================================================

    MESSAGE = "message"

    ACK = "ack"

    ERROR = "error"

    # =====================================================
    # Session / Ratchet
    # =====================================================

    SESSION_INIT = "session_init"

    SESSION_ACCEPT = "session_accept"

    SESSION_CLOSE = "session_close"

    REKEY = "rekey"

    RATCHET_STEP = "ratchet_step"

    # =====================================================
    # Transport lifecycle
    # =====================================================

    PING = "ping"

    PONG = "pong"

    CONNECT = "connect"

    DISCONNECT = "disconnect"

    # =====================================================
    # Attachments
    # =====================================================

    ATTACHMENT_META = "attachment_meta"

    ATTACHMENT_CHUNK = "attachment_chunk"

    ATTACHMENT_COMPLETE = (
        "attachment_complete"
    )

    # =====================================================
    # Presence / Sync
    # =====================================================

    PRESENCE = "presence"

    # Typing indicators
    TYPING_START = "typing_start"
    TYPING_STOP = "typing_stop"

    SYNC_REQUEST = "sync_request"

    SYNC_RESPONSE = "sync_response"

    # =====================================================
    # Internal / System
    # =====================================================

    SYSTEM = "system"

    EVENT = "event"


# =========================================================
# Packet Priority
# =========================================================

class PacketPriority(int, Enum):

    LOW = 1

    NORMAL = 5

    HIGH = 10

    CRITICAL = 100


# =========================================================
# Delivery State
# =========================================================

class PacketDeliveryState(str, Enum):

    PENDING = "pending"

    QUEUED = "queued"

    SENT = "sent"

    DELIVERED = "delivered"

    ACKED = "acked"

    FAILED = "failed"

    EXPIRED = "expired"

    DROPPED = "dropped"


# =========================================================
# Packet Flags
# =========================================================

FLAG_REQUIRES_ACK: Final[str] = (
    "requires_ack"
)

FLAG_ENCRYPTED: Final[str] = (
    "encrypted"
)

FLAG_REPLAY_PROTECTED: Final[str] = (
    "replay_protected"
)

FLAG_RATCHET_ENCRYPTED: Final[str] = (
    "ratchet_encrypted"
)

FLAG_FRAGMENTED: Final[str] = (
    "fragmented"
)

FLAG_COMPRESSED: Final[str] = (
    "compressed"
)

FLAG_PRIORITY: Final[str] = (
    "priority"
)


# =========================================================
# Packet Groups
# =========================================================

ACK_REQUIRED_PACKET_TYPES: Final[
    Set[PacketType]
] = {

    PacketType.MESSAGE,

    PacketType.ATTACHMENT_META,

    PacketType.ATTACHMENT_COMPLETE,

    PacketType.REKEY,

    PacketType.SESSION_INIT,

    PacketType.SESSION_ACCEPT,
}

ENCRYPTED_PACKET_TYPES: Final[
    Set[PacketType]
] = {

    PacketType.MESSAGE,

    PacketType.REKEY,

    PacketType.SESSION_INIT,

    PacketType.SESSION_ACCEPT,

    PacketType.ATTACHMENT_META,

    PacketType.ATTACHMENT_CHUNK,
}

SYSTEM_PACKET_TYPES: Final[
    Set[PacketType]
] = {

    PacketType.PING,

    PacketType.PONG,

    PacketType.CONNECT,

    PacketType.DISCONNECT,

    PacketType.SYSTEM,

    PacketType.EVENT,
}


# =========================================================
# Validators
# =========================================================

def is_valid_packet_type(
    value: str,
) -> bool:

    try:
        PacketType(value)
        return True

    except Exception:
        return False


def packet_requires_ack(
    packet_type: PacketType,
) -> bool:

    return (
        packet_type
        in ACK_REQUIRED_PACKET_TYPES
    )


def packet_requires_encryption(
    packet_type: PacketType,
) -> bool:

    return (
        packet_type
        in ENCRYPTED_PACKET_TYPES
    )


def is_system_packet(
    packet_type: PacketType,
) -> bool:

    return (
        packet_type
        in SYSTEM_PACKET_TYPES
    )


# =========================================================
# Helpers
# =========================================================

def normalize_packet_type(
    value: str | PacketType,
) -> PacketType:

    if isinstance(
        value,
        PacketType,
    ):
        return value

    return PacketType(
        value.strip().lower()
    )


__all__ = [

    # enums
    "PacketType",
    "PacketPriority",
    "PacketDeliveryState",

    # flags
    "FLAG_REQUIRES_ACK",
    "FLAG_ENCRYPTED",
    "FLAG_REPLAY_PROTECTED",
    "FLAG_RATCHET_ENCRYPTED",
    "FLAG_FRAGMENTED",
    "FLAG_COMPRESSED",
    "FLAG_PRIORITY",

    # packet groups
    "ACK_REQUIRED_PACKET_TYPES",
    "ENCRYPTED_PACKET_TYPES",
    "SYSTEM_PACKET_TYPES",

    # validators
    "is_valid_packet_type",
    "packet_requires_ack",
    "packet_requires_encryption",
    "is_system_packet",

    # helpers
    "normalize_packet_type",
]
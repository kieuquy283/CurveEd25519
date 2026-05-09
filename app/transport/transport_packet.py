from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


# =========================================================
# Types
# =========================================================

JsonDict = Dict[str, Any]


# =========================================================
# Exceptions
# =========================================================

class TransportPacketError(Exception):
    """Base transport packet exception."""


class InvalidTransportPacketError(
    TransportPacketError
):
    """Transport packet invalid."""


# =========================================================
# Packet Types
# =========================================================

class TransportPacketType(str, Enum):

    # Core messaging
    MESSAGE = "message"

    # ACK flow
    ACK = "ack"

    # Keepalive
    PING = "ping"
    PONG = "pong"

    # Session lifecycle
    SESSION_INIT = "session_init"
    SESSION_REKEY = "session_rekey"
    SESSION_CLOSE = "session_close"

    # Presence/events
    PRESENCE = "presence"
    TYPING = "typing"

    # Attachments
    ATTACHMENT = "attachment"

    # Error
    ERROR = "error"


# =========================================================
# Packet Metadata
# =========================================================

@dataclass(slots=True)
class TransportMetadata:
    """
    Optional transport-level metadata.
    """

    trace_id: Optional[str] = None

    route: Optional[str] = None

    ttl_seconds: Optional[int] = None

    compression: Optional[str] = None

    content_type: Optional[str] = None

    custom: JsonDict = field(
        default_factory=dict
    )

    def to_dict(self) -> JsonDict:

        return {
            "trace_id": self.trace_id,
            "route": self.route,
            "ttl_seconds": self.ttl_seconds,
            "compression": self.compression,
            "content_type": self.content_type,
            "custom": self.custom,
        }

    @classmethod
    def from_dict(
        cls,
        data: JsonDict,
    ) -> "TransportMetadata":

        return cls(
            trace_id=data.get(
                "trace_id"
            ),

            route=data.get(
                "route"
            ),

            ttl_seconds=data.get(
                "ttl_seconds"
            ),

            compression=data.get(
                "compression"
            ),

            content_type=data.get(
                "content_type"
            ),

            custom=dict(
                data.get(
                    "custom",
                    {},
                )
            ),
        )


# =========================================================
# Transport Packet
# =========================================================

@dataclass(slots=True, init=False)
class TransportPacket:
    """
    Network transport packet.

    This wraps protocol-level payloads:
    - encrypted envelopes
    - ACKs
    - session events
    - presence events

    Layering:
    -------------------------------------
    UI
      ↓
    DeliveryService
      ↓
    ProtocolService
      ↓
    TransportPacket
      ↓
    WebSocket/TCP
    """

    packet_type: TransportPacketType

    sender_id: str

    receiver_id: str

    payload: JsonDict

    packet_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    created_at: str = field(default_factory=lambda: (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    ))

    metadata: TransportMetadata = field(default_factory=TransportMetadata)

    protocol_version: int = 1

    requires_ack: bool = True

    encrypted: bool = True

    compressed: bool = False

    priority: int = 0

    def __init__(
        self,
        *,
        packet_type: TransportPacketType,
        payload: JsonDict,
        sender_id: str | None = None,
        receiver_id: str | None = None,
        sender_peer_id: str | None = None,
        receiver_peer_id: str | None = None,
        packet_id: str | None = None,
        created_at: str | None = None,
        metadata: TransportMetadata | None = None,
        protocol_version: int = 1,
        requires_ack: bool = True,
        encrypted: bool = True,
        compressed: bool = False,
        priority: int = 0,
    ) -> None:

        # accept either sender_id or sender_peer_id
        sid = sender_id if sender_id is not None else sender_peer_id
        rid = receiver_id if receiver_id is not None else receiver_peer_id

        if sid is None or rid is None:
            raise InvalidTransportPacketError("sender_id and receiver_id required")

        self.packet_type = packet_type
        self.sender_id = sid
        self.receiver_id = rid
        self.payload = payload
        self.packet_id = packet_id or str(uuid.uuid4())
        self.created_at = created_at or (
            datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
        self.metadata = metadata or TransportMetadata()
        self.protocol_version = protocol_version
        self.requires_ack = requires_ack
        self.encrypted = encrypted
        self.compressed = compressed
        self.priority = priority
        # compatibility aliases expected by tests
        self.sender_peer_id = self.sender_id
        self.receiver_peer_id = self.receiver_id

    @property
    def sender_peer_id(self) -> str:  # type: ignore[override]
        return self.sender_id

    @sender_peer_id.setter
    def sender_peer_id(self, v: str) -> None:
        self.sender_id = v

    @property
    def receiver_peer_id(self) -> str:  # type: ignore[override]
        return self.receiver_id

    @receiver_peer_id.setter
    def receiver_peer_id(self, v: str) -> None:
        self.receiver_id = v

    # =====================================================
    # Serialization
    # =====================================================

    def to_dict(self) -> JsonDict:

        return {
            "packet_id": self.packet_id,

            "packet_type": (
                self.packet_type.value
            ),

            "protocol_version":
                self.protocol_version,

            "sender_id":
                self.sender_id,

            "receiver_id":
                self.receiver_id,

            "created_at":
                self.created_at,

            "requires_ack":
                self.requires_ack,

            "encrypted":
                self.encrypted,

            "compressed":
                self.compressed,

            "priority":
                self.priority,

            "metadata":
                self.metadata.to_dict(),

            "payload":
                self.payload,
        }

    def to_json(self) -> str:

        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def to_bytes(self) -> bytes:

        return self.to_json().encode(
            "utf-8"
        )

    # =====================================================
    # Validation
    # =====================================================

    def validate(self) -> None:

        if not isinstance(
            self.packet_type,
            TransportPacketType,
        ):
            raise (
                InvalidTransportPacketError(
                    "Invalid packet_type."
                )
            )

        if not self.sender_id:
            raise (
                InvalidTransportPacketError(
                    "sender_id required."
                )
            )

        if not self.receiver_id:
            raise (
                InvalidTransportPacketError(
                    "receiver_id required."
                )
            )

        if not isinstance(
            self.payload,
            dict,
        ):
            raise (
                InvalidTransportPacketError(
                    "payload must be dict."
                )
            )

        if not self.packet_id:
            raise (
                InvalidTransportPacketError(
                    "packet_id required."
                )
            )

    # =====================================================
    # Factories
    # =====================================================

    @classmethod
    def from_dict(
        cls,
        data: JsonDict,
    ) -> "TransportPacket":

        try:

            metadata = (
                TransportMetadata
                .from_dict(
                    data.get(
                        "metadata",
                        {},
                    )
                )
            )

            packet = cls(
                packet_id=data[
                    "packet_id"
                ],

                packet_type=(
                    TransportPacketType(
                        data[
                            "packet_type"
                        ]
                    )
                ),

                protocol_version=data.get(
                    "protocol_version",
                    1,
                ),

                sender_id=data[
                    "sender_id"
                ],

                receiver_id=data[
                    "receiver_id"
                ],

                created_at=data[
                    "created_at"
                ],

                requires_ack=data.get(
                    "requires_ack",
                    True,
                ),

                encrypted=data.get(
                    "encrypted",
                    True,
                ),

                compressed=data.get(
                    "compressed",
                    False,
                ),

                priority=data.get(
                    "priority",
                    0,
                ),

                metadata=metadata,

                payload=dict(
                    data[
                        "payload"
                    ]
                ),
            )

            packet.validate()

            return packet

        except KeyError as exc:

            raise (
                InvalidTransportPacketError(
                    f"Missing field: "
                    f"{exc}"
                )
            ) from exc

        except Exception as exc:

            raise (
                InvalidTransportPacketError(
                    str(exc)
                )
            ) from exc

    @classmethod
    def from_json(
        cls,
        raw_json: str,
    ) -> "TransportPacket":

        try:

            data = json.loads(
                raw_json
            )

        except Exception as exc:

            raise (
                InvalidTransportPacketError(
                    "Invalid JSON packet."
                )
            ) from exc

        return cls.from_dict(data)

    @classmethod
    def from_bytes(
        cls,
        raw_bytes: bytes,
    ) -> "TransportPacket":

        try:

            raw_json = (
                raw_bytes.decode(
                    "utf-8"
                )
            )

        except Exception as exc:

            raise (
                InvalidTransportPacketError(
                    "Invalid UTF-8 packet."
                )
            ) from exc

        return cls.from_json(
            raw_json
        )

    # =====================================================
    # Convenience Builders
    # =====================================================

    @classmethod
    def build_message_packet(
        cls,
        *,
        sender_id: str,
        receiver_id: str,
        envelope: JsonDict,
    ) -> "TransportPacket":

        return cls(
            packet_type=(
                TransportPacketType
                .MESSAGE
            ),

            sender_id=sender_id,

            receiver_id=receiver_id,

            payload={
                "envelope":
                    envelope
            },

            encrypted=True,

            requires_ack=True,
        )

    @classmethod
    def build_ack_packet(
        cls,
        *,
        sender_id: str,
        receiver_id: str,
        message_id: str,
    ) -> "TransportPacket":

        return cls(
            packet_type=(
                TransportPacketType
                .ACK
            ),

            sender_id=sender_id,

            receiver_id=receiver_id,

            encrypted=False,

            requires_ack=False,

            payload={
                "message_id":
                    message_id
            },
        )

    @classmethod
    def build_ping_packet(
        cls,
        *,
        sender_id: str,
        receiver_id: str,
    ) -> "TransportPacket":

        return cls(
            packet_type=(
                TransportPacketType
                .PING
            ),

            sender_id=sender_id,

            receiver_id=receiver_id,

            encrypted=False,

            requires_ack=False,

            payload={},
        )

    @classmethod
    def build_pong_packet(
        cls,
        *,
        sender_id: str,
        receiver_id: str,
    ) -> "TransportPacket":

        return cls(
            packet_type=(
                TransportPacketType
                .PONG
            ),

            sender_id=sender_id,

            receiver_id=receiver_id,

            encrypted=False,

            requires_ack=False,

            payload={},
        )

    @classmethod
    def build_error_packet(
        cls,
        *,
        sender_id: str,
        receiver_id: str,
        error_code: str,
        message: str,
    ) -> "TransportPacket":

        return cls(
            packet_type=(
                TransportPacketType
                .ERROR
            ),

            sender_id=sender_id,

            receiver_id=receiver_id,

            encrypted=False,

            requires_ack=False,

            payload={
                "error_code":
                    error_code,

                "message":
                    message,
            },
        )

    # =====================================================
    # Utilities
    # =====================================================

    @property
    def is_message(self) -> bool:

        return (
            self.packet_type
            == TransportPacketType.MESSAGE
        )

    @property
    def is_ack(self) -> bool:

        return (
            self.packet_type
            == TransportPacketType.ACK
        )

    @property
    def is_ping(self) -> bool:

        return (
            self.packet_type
            == TransportPacketType.PING
        )

    @property
    def is_pong(self) -> bool:

        return (
            self.packet_type
            == TransportPacketType.PONG
        )

    @property
    def is_error(self) -> bool:

        return (
            self.packet_type
            == TransportPacketType.ERROR
        )


# =========================================================
# Public Exports
# =========================================================

__all__ = [
    "TransportPacketError",
    "InvalidTransportPacketError",

    "TransportPacketType",

    "TransportMetadata",

    "TransportPacket",
]
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


# =========================================================
# Event Types
# =========================================================

class TransportEventType(
    str,
    Enum,
):

    # =====================================================
    # Connection lifecycle
    # =====================================================

    CONNECTING = "connecting"

    CONNECTED = "connected"

    DISCONNECTED = "disconnected"

    RECONNECTING = "reconnecting"

    CONNECTION_FAILED = "connection_failed"

    CLOSED = "closed"

    # =====================================================
    # Authentication
    # =====================================================

    AUTH_STARTED = "auth_started"

    AUTH_SUCCESS = "auth_success"

    AUTH_FAILED = "auth_failed"

    # =====================================================
    # Messaging
    # =====================================================

    PACKET_RECEIVED = "packet_received"

    PACKET_SENT = "packet_sent"

    # Message-level aliases
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"

    PACKET_ACKED = "packet_acked"

    PACKET_DROPPED = "packet_dropped"

    # =====================================================
    # Queue
    # =====================================================

    QUEUE_ENQUEUED = "queue_enqueued"

    QUEUE_DEQUEUED = "queue_dequeued"

    QUEUE_RETRY = "queue_retry"

    QUEUE_FAILED = "queue_failed"

    # =====================================================
    # Session / Ratchet
    # =====================================================

    SESSION_CREATED = "session_created"

    SESSION_REKEYED = "session_rekeyed"

    SESSION_EXPIRED = "session_expired"

    RATCHET_ADVANCED = "ratchet_advanced"

    # =====================================================
    # Replay / Security
    # =====================================================

    REPLAY_ATTACK_DETECTED = (
        "replay_attack_detected"
    )

    SIGNATURE_INVALID = (
        "signature_invalid"
    )

    DECRYPTION_FAILED = (
        "decryption_failed"
    )

    NONCE_REUSE_DETECTED = (
        "nonce_reuse_detected"
    )

    # =====================================================
    # Attachments
    # =====================================================

    ATTACHMENT_UPLOAD_STARTED = (
        "attachment_upload_started"
    )

    ATTACHMENT_UPLOAD_COMPLETED = (
        "attachment_upload_completed"
    )

    ATTACHMENT_DOWNLOAD_STARTED = (
        "attachment_download_started"
    )

    ATTACHMENT_DOWNLOAD_COMPLETED = (
        "attachment_download_completed"
    )

    # =====================================================
    # Internal
    # =====================================================

    HEARTBEAT = "heartbeat"

    ERROR = "error"

    WARNING = "warning"

    INFO = "info"

    # Typing events
    TYPING_STARTED = "typing_started"
    TYPING_STOPPED = "typing_stopped"


# =========================================================
# Event Severity
# =========================================================

class TransportEventSeverity(
    str,
    Enum,
):

    DEBUG = "debug"

    INFO = "info"

    WARNING = "warning"

    ERROR = "error"

    CRITICAL = "critical"


# =========================================================
# Transport Event
# =========================================================

@dataclass(slots=True)
class TransportEvent:
    """
    Generic transport-layer event.

    Architecture:
    ------------------------------------------------

        WebSocketTransport
                ↓
        ConnectionManager
                ↓
        EventBus / UI / Logging
    """

    event_type: TransportEventType

    timestamp: float = field(
        default_factory=time.time
    )

    severity: TransportEventSeverity = (
        TransportEventSeverity.INFO
    )

    # =====================================================
    # Routing
    # =====================================================

    peer_id: Optional[str] = None

    transport_id: Optional[str] = None

    session_id: Optional[str] = None

    packet_id: Optional[str] = None

    message_id: Optional[str] = None

    # =====================================================
    # Payload
    # =====================================================

    metadata: Dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    error_message: Optional[
        str
    ] = None

    exception_type: Optional[
        str
    ] = None

    # =====================================================
    # Helpers
    # =====================================================

    def is_error(self) -> bool:

        return self.severity in {
            TransportEventSeverity.ERROR,
            TransportEventSeverity.CRITICAL,
        }

    def is_warning(self) -> bool:

        return (
            self.severity
            == TransportEventSeverity.WARNING
        )

    def to_dict(self) -> dict:

        return {
            "event_type": (
                self.event_type.value
            ),

            "timestamp": (
                self.timestamp
            ),

            "severity": (
                self.severity.value
            ),

            "peer_id": (
                self.peer_id
            ),

            "transport_id": (
                self.transport_id
            ),

            "session_id": (
                self.session_id
            ),

            "packet_id": (
                self.packet_id
            ),

            "message_id": (
                self.message_id
            ),

            "metadata": (
                self.metadata
            ),

            "error_message": (
                self.error_message
            ),

            "exception_type": (
                self.exception_type
            ),
        }

    @classmethod
    def from_exception(
        cls,
        *,
        event_type: TransportEventType,
        exc: Exception,
        peer_id: Optional[str] = None,
        transport_id: Optional[str] = None,
        metadata: Optional[
            dict
        ] = None,
    ) -> "TransportEvent":

        return cls(
            event_type=event_type,

            severity=(
                TransportEventSeverity.ERROR
            ),

            peer_id=peer_id,

            transport_id=transport_id,

            metadata=metadata or {},

            error_message=str(exc),

            exception_type=(
                exc.__class__.__name__
            ),
        )


# =========================================================
# Factory Helpers
# =========================================================

def build_connected_event(
    *,
    peer_id: str,
    transport_id: str,
) -> TransportEvent:

    return TransportEvent(
        event_type=(
            TransportEventType.CONNECTED
        ),

        peer_id=peer_id,

        transport_id=transport_id,

        severity=(
            TransportEventSeverity.INFO
        ),
    )


def build_disconnected_event(
    *,
    peer_id: str,
    transport_id: str,
    reason: Optional[str] = None,
) -> TransportEvent:

    return TransportEvent(
        event_type=(
            TransportEventType.DISCONNECTED
        ),

        peer_id=peer_id,

        transport_id=transport_id,

        severity=(
            TransportEventSeverity.WARNING
        ),

        metadata={
            "reason": reason,
        },
    )


def build_packet_received_event(
    *,
    peer_id: str,
    packet_id: str,
    message_id: Optional[str] = None,
) -> TransportEvent:

    return TransportEvent(
        event_type=(
            TransportEventType.PACKET_RECEIVED
        ),

        peer_id=peer_id,

        packet_id=packet_id,

        message_id=message_id,

        severity=(
            TransportEventSeverity.DEBUG
        ),
    )


def build_packet_sent_event(
    *,
    peer_id: str,
    packet_id: str,
    message_id: Optional[str] = None,
) -> TransportEvent:

    return TransportEvent(
        event_type=(
            TransportEventType.PACKET_SENT
        ),

        peer_id=peer_id,

        packet_id=packet_id,

        message_id=message_id,

        severity=(
            TransportEventSeverity.DEBUG
        ),
    )


def build_security_event(
    *,
    event_type: TransportEventType,
    peer_id: Optional[str] = None,
    details: Optional[
        dict
    ] = None,
) -> TransportEvent:

    return TransportEvent(
        event_type=event_type,

        peer_id=peer_id,

        severity=(
            TransportEventSeverity.CRITICAL
        ),

        metadata=details or {},
    )


__all__ = [
    "TransportEventType",
    "TransportEventSeverity",
    "TransportEvent",

    "build_connected_event",
    "build_disconnected_event",

    "build_packet_received_event",
    "build_packet_sent_event",

    "build_security_event",
]
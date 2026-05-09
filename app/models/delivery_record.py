from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


# =========================================================
# Delivery States
# =========================================================

class DeliveryState(str, Enum):
    """
    Message delivery lifecycle.
    """

    # -----------------------------------------------------
    # Local states
    # -----------------------------------------------------

    QUEUED = "queued"

    ENCRYPTING = "encrypting"

    ENCRYPTED = "encrypted"

    SENDING = "sending"

    SENT = "sent"

    RETRY_PENDING = "retry_pending"

    FAILED = "failed"

    DEAD_LETTER = "dead_letter"

    CANCELLED = "cancelled"

    # -----------------------------------------------------
    # Remote states
    # -----------------------------------------------------

    RECEIVED = "received"

    VERIFIED = "verified"

    DECRYPTED = "decrypted"

    STORED = "stored"

    DELIVERED = "delivered"

    READ = "read"


# =========================================================
# Delivery Priority
# =========================================================

class DeliveryPriority(str, Enum):

    LOW = "low"

    NORMAL = "normal"

    HIGH = "high"

    CRITICAL = "critical"


# =========================================================
# Delivery Record
# =========================================================

@dataclass(slots=True)
class DeliveryRecord:
    """
    Delivery tracking record.

    Responsibilities:
    - queue state tracking
    - retry metadata
    - ACK lifecycle
    - transport state
    - timing metrics

    Persisted in:
        queue_store.py
    """

    # =====================================================
    # Core identity
    # =====================================================

    message_id: str

    sender_id: str

    receiver_id: str

    # =====================================================
    # Session metadata
    # =====================================================

    session_id: Optional[str] = None

    conversation_id: Optional[str] = None

    # =====================================================
    # State
    # =====================================================

    state: DeliveryState = (
        DeliveryState.QUEUED
    )

    priority: DeliveryPriority = (
        DeliveryPriority.NORMAL
    )

    # =====================================================
    # Payload
    # =====================================================

    plaintext_preview: Optional[str] = None

    encrypted_envelope_json: Optional[str] = None

    attachment_id: Optional[str] = None

    attachment_count: int = 0

    # =====================================================
    # Retry metadata
    # =====================================================

    retry_count: int = 0

    max_retries: int = 5

    retry_backoff_seconds: int = 1

    next_retry_at: Optional[str] = None

    last_error: Optional[str] = None

    # =====================================================
    # ACK metadata
    # =====================================================

    ack_required: bool = True

    ack_received: bool = False

    ack_message_id: Optional[str] = None

    delivered_at: Optional[str] = None

    read_at: Optional[str] = None

    # =====================================================
    # Timestamps
    # =====================================================

    created_at: str = field(
        default_factory=lambda: (
            DeliveryRecord.utc_now_iso()
        )
    )

    updated_at: str = field(
        default_factory=lambda: (
            DeliveryRecord.utc_now_iso()
        )
    )

    queued_at: str = field(
        default_factory=lambda: (
            DeliveryRecord.utc_now_iso()
        )
    )

    sent_at: Optional[str] = None

    failed_at: Optional[str] = None

    # =====================================================
    # Metrics
    # =====================================================

    processing_time_ms: Optional[int] = None

    transport_latency_ms: Optional[int] = None

    # =====================================================
    # Flags
    # =====================================================

    is_offline_queued: bool = False

    is_duplicate: bool = False

    is_replayed: bool = False

    is_expired: bool = False

    # =====================================================
    # Security
    # =====================================================

    ratchet_key_id: Optional[str] = None

    replay_key: Optional[str] = None

    nonce_id: Optional[str] = None

    # =====================================================
    # Custom metadata
    # =====================================================

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    # =====================================================
    # State helpers
    # =====================================================

    def mark_encrypting(self) -> None:

        self.state = (
            DeliveryState.ENCRYPTING
        )

        self.touch()

    def mark_encrypted(self) -> None:

        self.state = (
            DeliveryState.ENCRYPTED
        )

        self.touch()

    def mark_sending(self) -> None:

        self.state = (
            DeliveryState.SENDING
        )

        self.touch()

    def mark_sent(self) -> None:

        self.state = (
            DeliveryState.SENT
        )

        self.sent_at = (
            self.utc_now_iso()
        )

        self.touch()

    def mark_delivered(self) -> None:

        self.state = (
            DeliveryState.DELIVERED
        )

        self.ack_received = True

        self.delivered_at = (
            self.utc_now_iso()
        )

        self.touch()

    def mark_read(self) -> None:

        self.state = (
            DeliveryState.READ
        )

        self.read_at = (
            self.utc_now_iso()
        )

        self.touch()

    def mark_failed(
        self,
        error: str,
    ) -> None:

        self.state = (
            DeliveryState.FAILED
        )

        self.last_error = error

        self.failed_at = (
            self.utc_now_iso()
        )

        self.touch()

    def mark_retry_pending(
        self,
        next_retry_at: str,
    ) -> None:

        self.state = (
            DeliveryState.RETRY_PENDING
        )

        self.next_retry_at = (
            next_retry_at
        )

        self.retry_count += 1

        self.touch()

    def mark_dead_letter(
        self,
        error: str,
    ) -> None:

        self.state = (
            DeliveryState.DEAD_LETTER
        )

        self.last_error = error

        self.touch()

    # =====================================================
    # Retry helpers
    # =====================================================

    def can_retry(self) -> bool:

        return (
            self.retry_count
            < self.max_retries
        )

    def compute_backoff_seconds(
        self,
    ) -> int:
        """
        Exponential backoff.

        Example:
            1,2,4,8,16...
        """

        return (
            self.retry_backoff_seconds
            * (2 ** self.retry_count)
        )

    # =====================================================
    # ACK helpers
    # =====================================================

    def requires_ack(self) -> bool:

        return self.ack_required

    def is_acknowledged(self) -> bool:

        return self.ack_received

    # =====================================================
    # Queue helpers
    # =====================================================

    def is_terminal_state(self) -> bool:

        return self.state in {
            DeliveryState.DELIVERED,
            DeliveryState.READ,
            DeliveryState.CANCELLED,
            DeliveryState.DEAD_LETTER,
        }

    def is_failed(self) -> bool:

        return self.state in {
            DeliveryState.FAILED,
            DeliveryState.DEAD_LETTER,
        }

    def is_pending(self) -> bool:

        return self.state in {
            DeliveryState.QUEUED,
            DeliveryState.ENCRYPTING,
            DeliveryState.ENCRYPTED,
            DeliveryState.SENDING,
            DeliveryState.RETRY_PENDING,
        }

    # =====================================================
    # Timestamp helpers
    # =====================================================

    def touch(self) -> None:

        self.updated_at = (
            self.utc_now_iso()
        )

    # =====================================================
    # Serialization
    # =====================================================

    def to_dict(self) -> Dict[str, Any]:

        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,

            "session_id": self.session_id,
            "conversation_id": self.conversation_id,

            "state": self.state.value,
            "priority": self.priority.value,

            "plaintext_preview":
                self.plaintext_preview,

            "encrypted_envelope_json":
                self.encrypted_envelope_json,

            "attachment_id":
                self.attachment_id,

            "attachment_count":
                self.attachment_count,

            "retry_count":
                self.retry_count,

            "max_retries":
                self.max_retries,

            "retry_backoff_seconds":
                self.retry_backoff_seconds,

            "next_retry_at":
                self.next_retry_at,

            "last_error":
                self.last_error,

            "ack_required":
                self.ack_required,

            "ack_received":
                self.ack_received,

            "ack_message_id":
                self.ack_message_id,

            "delivered_at":
                self.delivered_at,

            "read_at":
                self.read_at,

            "created_at":
                self.created_at,

            "updated_at":
                self.updated_at,

            "queued_at":
                self.queued_at,

            "sent_at":
                self.sent_at,

            "failed_at":
                self.failed_at,

            "processing_time_ms":
                self.processing_time_ms,

            "transport_latency_ms":
                self.transport_latency_ms,

            "is_offline_queued":
                self.is_offline_queued,

            "is_duplicate":
                self.is_duplicate,

            "is_replayed":
                self.is_replayed,

            "is_expired":
                self.is_expired,

            "ratchet_key_id":
                self.ratchet_key_id,

            "replay_key":
                self.replay_key,

            "nonce_id":
                self.nonce_id,

            "metadata":
                self.metadata,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
    ) -> "DeliveryRecord":

        return cls(
            message_id=data["message_id"],

            sender_id=data["sender_id"],
            receiver_id=data["receiver_id"],

            session_id=data.get(
                "session_id"
            ),

            conversation_id=data.get(
                "conversation_id"
            ),

            state=DeliveryState(
                data.get(
                    "state",
                    DeliveryState.QUEUED.value,
                )
            ),

            priority=DeliveryPriority(
                data.get(
                    "priority",
                    DeliveryPriority.NORMAL.value,
                )
            ),

            plaintext_preview=data.get(
                "plaintext_preview"
            ),

            encrypted_envelope_json=data.get(
                "encrypted_envelope_json"
            ),

            attachment_id=data.get(
                "attachment_id"
            ),

            attachment_count=int(
                data.get(
                    "attachment_count",
                    0,
                )
            ),

            retry_count=int(
                data.get(
                    "retry_count",
                    0,
                )
            ),

            max_retries=int(
                data.get(
                    "max_retries",
                    5,
                )
            ),

            retry_backoff_seconds=int(
                data.get(
                    "retry_backoff_seconds",
                    1,
                )
            ),

            next_retry_at=data.get(
                "next_retry_at"
            ),

            last_error=data.get(
                "last_error"
            ),

            ack_required=bool(
                data.get(
                    "ack_required",
                    True,
                )
            ),

            ack_received=bool(
                data.get(
                    "ack_received",
                    False,
                )
            ),

            ack_message_id=data.get(
                "ack_message_id"
            ),

            delivered_at=data.get(
                "delivered_at"
            ),

            read_at=data.get(
                "read_at"
            ),

            created_at=data.get(
                "created_at",
                cls.utc_now_iso(),
            ),

            updated_at=data.get(
                "updated_at",
                cls.utc_now_iso(),
            ),

            queued_at=data.get(
                "queued_at",
                cls.utc_now_iso(),
            ),

            sent_at=data.get(
                "sent_at"
            ),

            failed_at=data.get(
                "failed_at"
            ),

            processing_time_ms=data.get(
                "processing_time_ms"
            ),

            transport_latency_ms=data.get(
                "transport_latency_ms"
            ),

            is_offline_queued=bool(
                data.get(
                    "is_offline_queued",
                    False,
                )
            ),

            is_duplicate=bool(
                data.get(
                    "is_duplicate",
                    False,
                )
            ),

            is_replayed=bool(
                data.get(
                    "is_replayed",
                    False,
                )
            ),

            is_expired=bool(
                data.get(
                    "is_expired",
                    False,
                )
            ),

            ratchet_key_id=data.get(
                "ratchet_key_id"
            ),

            replay_key=data.get(
                "replay_key"
            ),

            nonce_id=data.get(
                "nonce_id"
            ),

            metadata=dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )

    # =====================================================
    # Utilities
    # =====================================================

    @staticmethod
    def utc_now_iso() -> str:

        return (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
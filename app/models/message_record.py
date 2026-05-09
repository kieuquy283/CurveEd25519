from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


JsonDict = Dict[str, Any]


# =========================================================
# Message Direction
# =========================================================

class MessageDirection(str, Enum):
    """
    Message flow direction.
    """

    INBOUND = "inbound"

    OUTBOUND = "outbound"


# =========================================================
# Delivery State
# =========================================================

class MessageState(str, Enum):
    """
    Message lifecycle state.
    """

    PENDING = "pending"

    SENT = "sent"

    DELIVERED = "delivered"

    READ = "read"

    FAILED = "failed"

    EXPIRED = "expired"


# =========================================================
# Attachment Metadata
# =========================================================

@dataclass(slots=True)
class AttachmentReference:
    """
    Message attachment reference.
    """

    attachment_id: str

    filename: str

    media_type: str

    size_bytes: int

    sha256: str

    encrypted: bool = True

    storage_path: Optional[str] = None

    metadata: JsonDict = field(
        default_factory=dict
    )

    def to_dict(self) -> JsonDict:

        return {
            "attachment_id": (
                self.attachment_id
            ),
            "filename": self.filename,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "encrypted": self.encrypted,
            "storage_path": (
                self.storage_path
            ),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(
        cls,
        data: JsonDict,
    ) -> "AttachmentReference":

        return cls(
            attachment_id=data[
                "attachment_id"
            ],
            filename=data["filename"],
            media_type=data[
                "media_type"
            ],
            size_bytes=data[
                "size_bytes"
            ],
            sha256=data["sha256"],
            encrypted=data.get(
                "encrypted",
                True,
            ),
            storage_path=data.get(
                "storage_path"
            ),
            metadata=data.get(
                "metadata",
                {},
            ),
        )


# =========================================================
# Message Record
# =========================================================

@dataclass(slots=True)
class MessageRecord:
    """
    Persistent secure message model.

    This is the MAIN application-level
    message object.

    Contains:
    - protocol envelope
    - delivery state
    - attachments
    - metadata
    """

    # =====================================================
    # Core identifiers
    # =====================================================

    message_id: str

    conversation_id: str

    direction: MessageDirection

    # =====================================================
    # Participants
    # =====================================================

    sender_id: str

    receiver_id: str

    # =====================================================
    # Envelope
    # =====================================================

    encrypted_envelope: JsonDict

    # =====================================================
    # Plaintext (optional cache)
    #
    # NEVER sync remotely.
    # Local-device only.
    # =====================================================

    plaintext: Optional[str] = None

    # =====================================================
    # Delivery state
    # =====================================================

    state: MessageState = (
        MessageState.PENDING
    )

    # =====================================================
    # Attachments
    # =====================================================

    attachments: List[
        AttachmentReference
    ] = field(default_factory=list)

    # =====================================================
    # Timestamps
    # =====================================================

    created_at_unix: float = field(
        default_factory=lambda:
        datetime.now(
            timezone.utc
        ).timestamp()
    )

    updated_at_unix: float = field(
        default_factory=lambda:
        datetime.now(
            timezone.utc
        ).timestamp()
    )

    delivered_at_unix: Optional[
        float
    ] = None

    read_at_unix: Optional[
        float
    ] = None

    expires_at_unix: Optional[
        float
    ] = None

    # =====================================================
    # Ratchet metadata
    # =====================================================

    session_id: Optional[str] = None

    ratchet_step: Optional[int] = None

    # =====================================================
    # Local metadata
    # =====================================================

    local_only: bool = False

    starred: bool = False

    archived: bool = False

    deleted: bool = False

    # =====================================================
    # Custom extensible metadata
    # =====================================================

    metadata: JsonDict = field(
        default_factory=dict
    )

    # =====================================================
    # Helpers
    # =====================================================

    @property
    def has_attachments(self) -> bool:

        return bool(
            self.attachments
        )

    @property
    def is_inbound(self) -> bool:

        return (
            self.direction
            == MessageDirection.INBOUND
        )

    @property
    def is_outbound(self) -> bool:

        return (
            self.direction
            == MessageDirection.OUTBOUND
        )

    @property
    def is_read(self) -> bool:

        return (
            self.state
            == MessageState.READ
        )

    @property
    def is_delivered(self) -> bool:

        return (
            self.state
            in (
                MessageState.DELIVERED,
                MessageState.READ,
            )
        )

    # =====================================================
    # State transitions
    # =====================================================

    def mark_sent(self) -> None:

        self.state = MessageState.SENT

        self.updated_at_unix = (
            self._now()
        )

    def mark_delivered(self) -> None:

        now = self._now()

        self.state = (
            MessageState.DELIVERED
        )

        self.delivered_at_unix = now

        self.updated_at_unix = now

    def mark_read(self) -> None:

        now = self._now()

        self.state = MessageState.READ

        self.read_at_unix = now

        self.updated_at_unix = now

    def mark_failed(self) -> None:

        self.state = (
            MessageState.FAILED
        )

        self.updated_at_unix = (
            self._now()
        )

    def mark_expired(self) -> None:

        self.state = (
            MessageState.EXPIRED
        )

        self.updated_at_unix = (
            self._now()
        )

    # =====================================================
    # Serialization
    # =====================================================

    def to_dict(self) -> JsonDict:

        return {
            "message_id": (
                self.message_id
            ),
            "conversation_id": (
                self.conversation_id
            ),
            "direction": (
                self.direction.value
            ),
            "sender_id": (
                self.sender_id
            ),
            "receiver_id": (
                self.receiver_id
            ),
            "encrypted_envelope": (
                self.encrypted_envelope
            ),
            "plaintext": (
                self.plaintext
            ),
            "state": (
                self.state.value
            ),
            "attachments": [
                attachment.to_dict()
                for attachment
                in self.attachments
            ],
            "created_at_unix": (
                self.created_at_unix
            ),
            "updated_at_unix": (
                self.updated_at_unix
            ),
            "delivered_at_unix": (
                self.delivered_at_unix
            ),
            "read_at_unix": (
                self.read_at_unix
            ),
            "expires_at_unix": (
                self.expires_at_unix
            ),
            "session_id": (
                self.session_id
            ),
            "ratchet_step": (
                self.ratchet_step
            ),
            "local_only": (
                self.local_only
            ),
            "starred": (
                self.starred
            ),
            "archived": (
                self.archived
            ),
            "deleted": (
                self.deleted
            ),
            "metadata": (
                self.metadata
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: JsonDict,
    ) -> "MessageRecord":

        return cls(
            message_id=data[
                "message_id"
            ],

            conversation_id=data[
                "conversation_id"
            ],

            direction=MessageDirection(
                data["direction"]
            ),

            sender_id=data[
                "sender_id"
            ],

            receiver_id=data[
                "receiver_id"
            ],

            encrypted_envelope=data[
                "encrypted_envelope"
            ],

            plaintext=data.get(
                "plaintext"
            ),

            state=MessageState(
                data.get(
                    "state",
                    MessageState.PENDING.value,
                )
            ),

            attachments=[
                AttachmentReference.from_dict(
                    item
                )
                for item
                in data.get(
                    "attachments",
                    [],
                )
            ],

            created_at_unix=data.get(
                "created_at_unix",
                cls._now(),
            ),

            updated_at_unix=data.get(
                "updated_at_unix",
                cls._now(),
            ),

            delivered_at_unix=data.get(
                "delivered_at_unix"
            ),

            read_at_unix=data.get(
                "read_at_unix"
            ),

            expires_at_unix=data.get(
                "expires_at_unix"
            ),

            session_id=data.get(
                "session_id"
            ),

            ratchet_step=data.get(
                "ratchet_step"
            ),

            local_only=data.get(
                "local_only",
                False,
            ),

            starred=data.get(
                "starred",
                False,
            ),

            archived=data.get(
                "archived",
                False,
            ),

            deleted=data.get(
                "deleted",
                False,
            ),

            metadata=data.get(
                "metadata",
                {},
            ),
        )

    # =====================================================
    # Utilities
    # =====================================================

    @staticmethod
    def _now() -> float:

        return datetime.now(
            timezone.utc
        ).timestamp()


__all__ = [
    "MessageDirection",
    "MessageState",
    "AttachmentReference",
    "MessageRecord",
]
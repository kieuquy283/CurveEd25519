from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional


# =========================================================
# Constants
# =========================================================

DEFAULT_SESSION_TTL_SECONDS = 86400
DEFAULT_MAX_MESSAGES_PER_CHAIN = 1000


# =========================================================
# Exceptions
# =========================================================

class SessionError(Exception):
    """Base session exception."""


class InvalidSessionError(SessionError):
    """Session structure invalid."""


class SessionExpiredError(SessionError):
    """Session expired."""


class SessionClosedError(SessionError):
    """Session already closed."""


# =========================================================
# Enums
# =========================================================

class SessionStatus(str, Enum):
    """
    Session lifecycle state.
    """

    ACTIVE = "active"

    EXPIRED = "expired"

    CLOSED = "closed"

    COMPROMISED = "compromised"


class SessionDirection(str, Enum):
    """
    Session ownership direction.
    """

    INITIATOR = "initiator"

    RESPONDER = "responder"


# =========================================================
# Ratchet State
# =========================================================

@dataclass(slots=True)
class RatchetState:
    """
    Future Double Ratchet compatibility.

    Current implementation:
    - placeholder state container
    - prepared for DH ratchet extension
    """

    dh_ratchet_public_key_b64: Optional[str] = None

    previous_chain_length: int = 0

    sending_chain_index: int = 0

    receiving_chain_index: int = 0

    last_ratchet_at_unix: float = field(
        default_factory=time.time
    )


# =========================================================
# Message Counters
# =========================================================

@dataclass(slots=True)
class SessionCounters:
    """
    Session message counters.

    Used for:
    - replay isolation
    - rekey thresholds
    - ratchet preparation
    """

    sent_messages: int = 0

    received_messages: int = 0

    send_chain_counter: int = 0

    receive_chain_counter: int = 0

    skipped_messages: int = 0

    failed_decryptions: int = 0

    last_sent_at_unix: Optional[float] = None

    last_received_at_unix: Optional[float] = None

    def increment_sent(self) -> None:
        self.sent_messages += 1
        self.send_chain_counter += 1
        self.last_sent_at_unix = time.time()

    def increment_received(self) -> None:
        self.received_messages += 1
        self.receive_chain_counter += 1
        self.last_received_at_unix = time.time()

    def reset_send_chain(self) -> None:
        self.send_chain_counter = 0

    def reset_receive_chain(self) -> None:
        self.receive_chain_counter = 0


# =========================================================
# Session Model
# =========================================================

@dataclass(slots=True)
class Session:
    """
    Secure session state container.

    Responsibilities:
    - root/session key state
    - chain key lifecycle
    - expiration
    - replay isolation
    - ratchet preparation

    Thread safety:
    - handled externally by SessionStore
    """

    # =====================================================
    # Identity
    # =====================================================

    session_id: str

    local_user_id: str

    remote_user_id: str

    direction: SessionDirection

    status: SessionStatus = SessionStatus.ACTIVE

    # =====================================================
    # Cryptographic State
    # =====================================================

    root_key_b64: str = ""

    send_chain_key_b64: str = ""

    receive_chain_key_b64: str = ""

    session_salt_b64: Optional[str] = None

    # =====================================================
    # Fingerprints
    # =====================================================

    local_identity_fingerprint: Optional[str] = None

    remote_identity_fingerprint: Optional[str] = None

    remote_ephemeral_fingerprint: Optional[str] = None

    # =====================================================
    # Time State
    # =====================================================

    created_at_unix: float = field(
        default_factory=time.time
    )

    updated_at_unix: float = field(
        default_factory=time.time
    )

    expires_at_unix: float = field(
        default_factory=lambda: (
            time.time()
            + DEFAULT_SESSION_TTL_SECONDS
        )
    )

    last_activity_at_unix: float = field(
        default_factory=time.time
    )

    # =====================================================
    # Security Policy
    # =====================================================

    max_messages_per_chain: int = (
        DEFAULT_MAX_MESSAGES_PER_CHAIN
    )

    auto_rekey_enabled: bool = True

    allow_session_resumption: bool = False

    # =====================================================
    # Counters / Ratchet
    # =====================================================

    counters: SessionCounters = field(
        default_factory=SessionCounters
    )

    ratchet: RatchetState = field(
        default_factory=RatchetState
    )

    # =====================================================
    # Metadata
    # =====================================================

    metadata: Dict[str, str] = field(
        default_factory=dict
    )

    # =====================================================
    # Validation
    # =====================================================

    def validate(self) -> None:
        """
        Validate session integrity.
        """

        if not self.session_id.strip():
            raise InvalidSessionError(
                "session_id cannot be empty."
            )

        if not self.local_user_id.strip():
            raise InvalidSessionError(
                "local_user_id cannot be empty."
            )

        if not self.remote_user_id.strip():
            raise InvalidSessionError(
                "remote_user_id cannot be empty."
            )

        if (
            self.expires_at_unix
            <= self.created_at_unix
        ):
            raise InvalidSessionError(
                "expires_at_unix invalid."
            )

        if (
            self.max_messages_per_chain
            <= 0
        ):
            raise InvalidSessionError(
                "max_messages_per_chain must be > 0."
            )

    # =====================================================
    # Lifecycle
    # =====================================================

    def touch(self) -> None:
        """
        Update activity timestamp.
        """

        now = time.time()

        self.updated_at_unix = now

        self.last_activity_at_unix = now

    def is_expired(self) -> bool:
        """
        Session expiration check.
        """

        return (
            time.time()
            >= self.expires_at_unix
        )

    def ensure_active(self) -> None:
        """
        Validate session usability.
        """

        if self.status == SessionStatus.CLOSED:
            raise SessionClosedError(
                "Session is closed."
            )

        if self.status == SessionStatus.COMPROMISED:
            raise InvalidSessionError(
                "Session marked compromised."
            )

        if self.is_expired():
            self.status = SessionStatus.EXPIRED

            raise SessionExpiredError(
                "Session expired."
            )

    def close(self) -> None:
        """
        Close session permanently.
        """

        self.status = SessionStatus.CLOSED

        self.touch()

    def mark_compromised(self) -> None:
        """
        Mark compromised session.
        """

        self.status = SessionStatus.COMPROMISED

        self.touch()

    # =====================================================
    # Rekey Policy
    # =====================================================

    def should_rekey(self) -> bool:
        """
        Determine if chain rotation required.
        """

        if not self.auto_rekey_enabled:
            return False

        return (
            self.counters.send_chain_counter
            >= self.max_messages_per_chain
        )

    # =====================================================
    # Counters
    # =====================================================

    def register_sent_message(self) -> None:
        """
        Update sending counters.
        """

        self.ensure_active()

        self.counters.increment_sent()

        self.touch()

    def register_received_message(self) -> None:
        """
        Update receiving counters.
        """

        self.ensure_active()

        self.counters.increment_received()

        self.touch()

    # =====================================================
    # Serialization
    # =====================================================

    def to_dict(self) -> dict:
        """
        Safe export for storage layer.
        """

        return {
            "session_id": self.session_id,

            "local_user_id": self.local_user_id,

            "remote_user_id": self.remote_user_id,

            "direction": self.direction.value,

            "status": self.status.value,

            "root_key_b64": self.root_key_b64,

            "send_chain_key_b64":
                self.send_chain_key_b64,

            "receive_chain_key_b64":
                self.receive_chain_key_b64,

            "session_salt_b64":
                self.session_salt_b64,

            "local_identity_fingerprint":
                self.local_identity_fingerprint,

            "remote_identity_fingerprint":
                self.remote_identity_fingerprint,

            "remote_ephemeral_fingerprint":
                self.remote_ephemeral_fingerprint,

            "created_at_unix":
                self.created_at_unix,

            "updated_at_unix":
                self.updated_at_unix,

            "expires_at_unix":
                self.expires_at_unix,

            "last_activity_at_unix":
                self.last_activity_at_unix,

            "max_messages_per_chain":
                self.max_messages_per_chain,

            "auto_rekey_enabled":
                self.auto_rekey_enabled,

            "allow_session_resumption":
                self.allow_session_resumption,

            "counters": {
                "sent_messages":
                    self.counters.sent_messages,

                "received_messages":
                    self.counters.received_messages,

                "send_chain_counter":
                    self.counters.send_chain_counter,

                "receive_chain_counter":
                    self.counters.receive_chain_counter,

                "skipped_messages":
                    self.counters.skipped_messages,

                "failed_decryptions":
                    self.counters.failed_decryptions,

                "last_sent_at_unix":
                    self.counters.last_sent_at_unix,

                "last_received_at_unix":
                    self.counters.last_received_at_unix,
            },

            "ratchet": {
                "dh_ratchet_public_key_b64":
                    self.ratchet
                    .dh_ratchet_public_key_b64,

                "previous_chain_length":
                    self.ratchet
                    .previous_chain_length,

                "sending_chain_index":
                    self.ratchet
                    .sending_chain_index,

                "receiving_chain_index":
                    self.ratchet
                    .receiving_chain_index,

                "last_ratchet_at_unix":
                    self.ratchet
                    .last_ratchet_at_unix,
            },

            "metadata": self.metadata,
        }

    # =====================================================
    # Debug
    # =====================================================

    def summary(self) -> dict:
        """
        Safe debug summary.
        """

        return {
            "session_id": self.session_id,

            "participants": (
                f"{self.local_user_id}"
                f" <-> "
                f"{self.remote_user_id}"
            ),

            "status": self.status.value,

            "direction": self.direction.value,

            "expired": self.is_expired(),

            "sent_messages":
                self.counters.sent_messages,

            "received_messages":
                self.counters.received_messages,

            "created_at_iso":
                datetime.fromtimestamp(
                    self.created_at_unix,
                    tz=timezone.utc,
                ).isoformat(),

            "expires_at_iso":
                datetime.fromtimestamp(
                    self.expires_at_unix,
                    tz=timezone.utc,
                ).isoformat(),
        }


__all__ = [
    "SessionError",
    "InvalidSessionError",
    "SessionExpiredError",
    "SessionClosedError",

    "SessionStatus",
    "SessionDirection",

    "RatchetState",
    "SessionCounters",

    "Session",
]
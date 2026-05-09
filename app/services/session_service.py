from __future__ import annotations

import threading
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..core.session import (
    Session,
    SessionStatus,
)

from ..core.session_id import (
    generate_session_id,
)

from ..core.session_key import (
    SessionKeyMaterial,
    derive_initial_session_keys,
    derive_next_chain_key,
    derive_message_key,
)

from ..storage.session_store import (
    BaseSessionStore,
)

from ..storage.memory_session_store import (
    MemorySessionStore,
)

from ..core.x25519 import (
    derive_shared_secret_from_b64,
)


# =========================================================
# Constants
# =========================================================

DEFAULT_SESSION_TTL_SECONDS = 86400
DEFAULT_MAX_MESSAGES_PER_CHAIN = 1000


# =========================================================
# Exceptions
# =========================================================

class SessionServiceError(Exception):
    """Base session service exception."""


class SessionNotFoundError(SessionServiceError):
    """Session not found."""


class SessionExpiredError(SessionServiceError):
    """Session expired."""


class SessionClosedError(SessionServiceError):
    """Session closed."""


class SessionRotationRequired(SessionServiceError):
    """Session key rotation required."""


# =========================================================
# SessionService
# =========================================================

class SessionService:
    """
    High-level secure session orchestration.

    Responsibilities:
    - create sessions
    - load/save sessions
    - derive message keys
    - rotate chain keys
    - enforce expiration
    - manage session lifecycle

    Thread-safe.
    """

    def __init__(
        self,
        *,
        session_store: Optional[BaseSessionStore] = None,
        default_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        max_messages_per_chain: int = DEFAULT_MAX_MESSAGES_PER_CHAIN,
    ) -> None:

        self._store = (
            session_store
            or MemorySessionStore()
        )

        self.default_ttl_seconds = (
            default_ttl_seconds
        )

        self.max_messages_per_chain = (
            max_messages_per_chain
        )

        self._lock = threading.RLock()

    # =====================================================
    # Session Creation
    # =====================================================

    def create_session(
        self,
        *,
        local_user_id: str,
        remote_user_id: str,
        local_x25519_private_b64: str,
        remote_x25519_public_b64: str,
    ) -> Session:
        """
        Create secure session.

        Flow:
        - X25519 shared secret
        - derive root key
        - derive chain keys
        - persist session
        """

        with self._lock:

            shared_secret = (
                derive_shared_secret_from_b64(
                    private_key_b64=(
                        local_x25519_private_b64
                    ),
                    peer_public_key_b64=(
                        remote_x25519_public_b64
                    ),
                )
            )

            key_material = (
                derive_initial_session_keys(
                    shared_secret
                )
            )

            now = datetime.now(
                timezone.utc
            )

            expires_at = (
                now
                + timedelta(
                    seconds=(
                        self.default_ttl_seconds
                    )
                )
            )

            session = Session(
                session_id=generate_session_id(),

                local_user_id=local_user_id,
                remote_user_id=remote_user_id,

                status=SessionStatus.ACTIVE,

                created_at=now,
                updated_at=now,
                expires_at=expires_at,

                root_key=(
                    key_material.root_key
                ),

                send_chain_key=(
                    key_material.send_chain_key
                ),

                recv_chain_key=(
                    key_material.recv_chain_key
                ),

                send_message_index=0,
                recv_message_index=0,

                session_version=1,
            )

            self._store.save_session(
                session
            )

            return session

    # =====================================================
    # Session Retrieval
    # =====================================================

    def get_session(
        self,
        session_id: str,
    ) -> Session:

        session = (
            self._store.get_session(
                session_id
            )
        )

        if session is None:
            raise SessionNotFoundError(
                f"Session not found: "
                f"{session_id}"
            )

        self._ensure_session_usable(
            session
        )

        return session

    # =====================================================
    # Message Key Derivation
    # =====================================================

    def derive_outbound_message_key(
        self,
        session_id: str,
    ) -> tuple[bytes, int]:
        """
        Derive sending message key.

        Returns:
            (
                message_key,
                message_index
            )
        """

        with self._lock:

            session = self.get_session(
                session_id
            )

            if (
                session.send_message_index
                >= self.max_messages_per_chain
            ):
                raise SessionRotationRequired(
                    "Session send chain exhausted."
                )

            message_key = (
                derive_message_key(
                    session.send_chain_key,
                    session.send_message_index,
                )
            )

            next_chain_key = (
                derive_next_chain_key(
                    session.send_chain_key
                )
            )

            updated_session = replace(
                session,

                send_chain_key=(
                    next_chain_key
                ),

                send_message_index=(
                    session.send_message_index
                    + 1
                ),

                updated_at=(
                    datetime.now(
                        timezone.utc
                    )
                ),
            )

            self._store.update_session(
                updated_session
            )

            return (
                message_key,
                session.send_message_index,
            )

    def derive_inbound_message_key(
        self,
        session_id: str,
    ) -> tuple[bytes, int]:
        """
        Derive receiving message key.
        """

        with self._lock:

            session = self.get_session(
                session_id
            )

            if (
                session.recv_message_index
                >= self.max_messages_per_chain
            ):
                raise SessionRotationRequired(
                    "Session receive chain exhausted."
                )

            message_key = (
                derive_message_key(
                    session.recv_chain_key,
                    session.recv_message_index,
                )
            )

            next_chain_key = (
                derive_next_chain_key(
                    session.recv_chain_key
                )
            )

            updated_session = replace(
                session,

                recv_chain_key=(
                    next_chain_key
                ),

                recv_message_index=(
                    session.recv_message_index
                    + 1
                ),

                updated_at=(
                    datetime.now(
                        timezone.utc
                    )
                ),
            )

            self._store.update_session(
                updated_session
            )

            return (
                message_key,
                session.recv_message_index,
            )

    # =====================================================
    # Session Rotation
    # =====================================================

    def rotate_session(
        self,
        *,
        session_id: str,
        new_shared_secret: bytes,
    ) -> Session:
        """
        Rotate root + chain keys.
        """

        with self._lock:

            session = self.get_session(
                session_id
            )

            key_material = (
                derive_initial_session_keys(
                    new_shared_secret
                )
            )

            rotated = replace(
                session,

                root_key=(
                    key_material.root_key
                ),

                send_chain_key=(
                    key_material.send_chain_key
                ),

                recv_chain_key=(
                    key_material.recv_chain_key
                ),

                send_message_index=0,
                recv_message_index=0,

                session_version=(
                    session.session_version
                    + 1
                ),

                updated_at=(
                    datetime.now(
                        timezone.utc
                    )
                ),
            )

            self._store.update_session(
                rotated
            )

            return rotated

    # =====================================================
    # Session Lifecycle
    # =====================================================

    def close_session(
        self,
        session_id: str,
    ) -> None:

        with self._lock:

            session = self.get_session(
                session_id
            )

            closed = replace(
                session,

                status=(
                    SessionStatus.CLOSED
                ),

                updated_at=(
                    datetime.now(
                        timezone.utc
                    )
                ),
            )

            self._store.update_session(
                closed
            )

    def delete_session(
        self,
        session_id: str,
    ) -> None:

        with self._lock:

            self._store.delete_session(
                session_id
            )

    # =====================================================
    # Cleanup
    # =====================================================

    def cleanup_expired_sessions(
        self,
    ) -> int:
        """
        Cleanup expired sessions.
        """

        return (
            self._store.cleanup_expired()
        )

    # =====================================================
    # Validation
    # =====================================================

    def _ensure_session_usable(
        self,
        session: Session,
    ) -> None:

        if (
            session.status
            == SessionStatus.CLOSED
        ):
            raise SessionClosedError(
                f"Session closed: "
                f"{session.session_id}"
            )

        now = datetime.now(
            timezone.utc
        )

        if (
            session.expires_at
            <= now
        ):
            raise SessionExpiredError(
                f"Session expired: "
                f"{session.session_id}"
            )

    # =====================================================
    # Introspection
    # =====================================================

    def stats(self) -> dict:

        return {
            "store": (
                self._store.__class__.__name__
            ),

            "default_ttl_seconds": (
                self.default_ttl_seconds
            ),

            "max_messages_per_chain": (
                self.max_messages_per_chain
            ),
        }
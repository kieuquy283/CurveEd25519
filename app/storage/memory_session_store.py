from __future__ import annotations

import threading
import time
from dataclasses import replace
from typing import Dict, List, Optional, Final

from .session_store import (
    BaseSessionStore,
    SessionStoreError,
    SessionAlreadyExistsError,
    SessionNotFoundError,
)

from ..core.session import (
    Session,
    SessionStatus,
)


# =========================================================
# Constants
# =========================================================

DEFAULT_MAX_SESSIONS: Final[int] = 100_000

DEFAULT_CLEANUP_INTERVAL_SECONDS: Final[int] = 60


# =========================================================
# Memory Session Store
# =========================================================

class MemorySessionStore(BaseSessionStore):
    """
    High-performance in-memory session store.

    Features:
    - O(1) lookup
    - thread-safe
    - automatic expiration cleanup
    - bounded memory
    - session lifecycle management
    - efficient eviction
    - production-oriented architecture

    Internal Structures
    -------------------

    _sessions:
        session_id -> Session

    _participant_index:
        participant -> set(session_id)

    """

    def __init__(
        self,
        *,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        cleanup_interval_seconds: int = DEFAULT_CLEANUP_INTERVAL_SECONDS,
    ) -> None:

        if max_sessions <= 0:
            raise ValueError(
                "max_sessions must be > 0."
            )

        if cleanup_interval_seconds <= 0:
            raise ValueError(
                "cleanup_interval_seconds must be > 0."
            )

        self.max_sessions = max_sessions

        self.cleanup_interval_seconds = (
            cleanup_interval_seconds
        )

        self._sessions: Dict[
            str,
            Session,
        ] = {}

        self._participant_index: Dict[
            str,
            set[str],
        ] = {}

        self._lock = threading.RLock()

        self._last_cleanup_monotonic = (
            time.monotonic()
        )

    # =====================================================
    # Internal Helpers
    # =====================================================

    def _should_cleanup(self) -> bool:
        return (
            time.monotonic()
            - self._last_cleanup_monotonic
            >= self.cleanup_interval_seconds
        )

    def _mark_cleanup(self) -> None:
        self._last_cleanup_monotonic = (
            time.monotonic()
        )

    @staticmethod
    def _validate_session_id(
        session_id: str,
    ) -> str:

        if not isinstance(session_id, str):
            raise SessionStoreError(
                "session_id must be a string."
            )

        session_id = session_id.strip()

        if not session_id:
            raise SessionStoreError(
                "session_id cannot be empty."
            )

        return session_id

    @staticmethod
    def _is_expired(
        session: Session,
    ) -> bool:

        if session.expires_at_unix is None:
            return False

        return (
            time.time()
            >= session.expires_at_unix
        )

    def _index_session(
        self,
        session: Session,
    ) -> None:

        for participant in session.participants:

            bucket = self._participant_index.setdefault(
                participant,
                set(),
            )

            bucket.add(session.session_id)

    def _deindex_session(
        self,
        session: Session,
    ) -> None:

        for participant in session.participants:

            bucket = self._participant_index.get(
                participant
            )

            if bucket is None:
                continue

            bucket.discard(
                session.session_id
            )

            if not bucket:
                del self._participant_index[
                    participant
                ]

    def _evict_oldest_session(
        self,
    ) -> None:
        """
        Fallback eviction strategy.

        Evicts oldest-created session.
        """

        if not self._sessions:
            return

        oldest = min(
            self._sessions.values(),
            key=lambda s: s.created_at_unix,
        )

        self.delete_session(
            oldest.session_id
        )

    # =====================================================
    # CRUD Operations
    # =====================================================

    def save_session(
        self,
        session: Session,
    ) -> None:

        if not isinstance(
            session,
            Session,
        ):
            raise SessionStoreError(
                "session must be Session."
            )

        with self._lock:

            if self._should_cleanup():
                self.cleanup()

            if (
                session.session_id
                in self._sessions
            ):
                raise SessionAlreadyExistsError(
                    f"Session already exists: "
                    f"{session.session_id}"
                )

            if (
                len(self._sessions)
                >= self.max_sessions
            ):
                self.cleanup()

            if (
                len(self._sessions)
                >= self.max_sessions
            ):
                self._evict_oldest_session()

            self._sessions[
                session.session_id
            ] = session

            self._index_session(session)

    def get_session(
        self,
        session_id: str,
    ) -> Session:

        session_id = (
            self._validate_session_id(
                session_id
            )
        )

        with self._lock:

            session = self._sessions.get(
                session_id
            )

            if session is None:
                raise SessionNotFoundError(
                    f"Session not found: "
                    f"{session_id}"
                )

            if self._is_expired(session):

                self.delete_session(
                    session_id
                )

                raise SessionNotFoundError(
                    f"Session expired: "
                    f"{session_id}"
                )

            return session

    def update_session(
        self,
        session: Session,
    ) -> None:

        if not isinstance(
            session,
            Session,
        ):
            raise SessionStoreError(
                "session must be Session."
            )

        with self._lock:

            existing = self._sessions.get(
                session.session_id
            )

            if existing is None:
                raise SessionNotFoundError(
                    f"Session not found: "
                    f"{session.session_id}"
                )

            self._deindex_session(existing)

            self._sessions[
                session.session_id
            ] = session

            self._index_session(session)

    def delete_session(
        self,
        session_id: str,
    ) -> None:

        session_id = (
            self._validate_session_id(
                session_id
            )
        )

        with self._lock:

            session = self._sessions.pop(
                session_id,
                None,
            )

            if session is None:
                return

            self._deindex_session(session)

    # =====================================================
    # Lookup Operations
    # =====================================================

    def has_session(
        self,
        session_id: str,
    ) -> bool:

        session_id = (
            self._validate_session_id(
                session_id
            )
        )

        with self._lock:

            session = self._sessions.get(
                session_id
            )

            if session is None:
                return False

            if self._is_expired(session):

                self.delete_session(
                    session_id
                )

                return False

            return True

    def list_sessions(self) -> List[Session]:

        with self._lock:

            self.cleanup()

            return list(
                self._sessions.values()
            )

    def list_sessions_for_participant(
        self,
        participant: str,
    ) -> List[Session]:

        if not participant:
            return []

        with self._lock:

            session_ids = (
                self._participant_index.get(
                    participant,
                    set(),
                )
            )

            result: List[Session] = []

            expired_ids: List[str] = []

            for session_id in session_ids:

                session = self._sessions.get(
                    session_id
                )

                if session is None:
                    continue

                if self._is_expired(session):
                    expired_ids.append(
                        session_id
                    )
                    continue

                result.append(session)

            for expired_id in expired_ids:
                self.delete_session(
                    expired_id
                )

            return result

    # =====================================================
    # Session Lifecycle
    # =====================================================

    def mark_session_closed(
        self,
        session_id: str,
    ) -> None:

        with self._lock:

            session = self.get_session(
                session_id
            )

            updated = replace(
                session,
                status=SessionStatus.CLOSED,
            )

            self.update_session(
                updated
            )

    # =====================================================
    # Cleanup
    # =====================================================

    def cleanup(self) -> int:
        """
        Remove expired sessions.

        Complexity:
            O(n)
        """

        removed = 0

        with self._lock:

            expired = [
                session_id
                for session_id, session
                in self._sessions.items()
                if self._is_expired(session)
            ]

            for session_id in expired:

                self.delete_session(
                    session_id
                )

                removed += 1

            self._mark_cleanup()

        return removed

    def clear(self) -> None:

        with self._lock:

            self._sessions.clear()

            self._participant_index.clear()

    # =====================================================
    # Metrics / Debug
    # =====================================================

    def size(self) -> int:

        with self._lock:
            return len(self._sessions)

    def is_empty(self) -> bool:
        return self.size() == 0

    def stats(self) -> dict:

        with self._lock:

            active = 0
            expired = 0

            now = time.time()

            for session in (
                self._sessions.values()
            ):

                if (
                    session.expires_at_unix
                    is not None
                    and session.expires_at_unix
                    <= now
                ):
                    expired += 1
                else:
                    active += 1

            return {
                "active_sessions": active,
                "expired_sessions": expired,
                "total_sessions": len(
                    self._sessions
                ),
                "participants": len(
                    self._participant_index
                ),
                "max_sessions": (
                    self.max_sessions
                ),
                "cleanup_interval_seconds": (
                    self.cleanup_interval_seconds
                ),
            }

    def export_state(self) -> dict:
        """
        Debug export.

        Never expose in production APIs.
        """

        with self._lock:

            return {
                session_id: session.to_dict()
                for session_id, session
                in self._sessions.items()
            }


__all__ = [
    "MemorySessionStore",
]
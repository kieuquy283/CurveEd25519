from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from typing import Dict, Iterable, Optional, Protocol

from ..core.session import (
    Session,
    SessionStatus,
)


# =========================================================
# Exceptions
# =========================================================

class SessionStoreError(Exception):
    """Base session store exception."""


class SessionNotFoundError(SessionStoreError):
    """Session not found."""


class SessionAlreadyExistsError(SessionStoreError):
    """Session already exists."""


class InvalidSessionError(SessionStoreError):
    """Invalid session object."""


# =========================================================
# Session Store Interface
# =========================================================

class BaseSessionStore(ABC):
    """
    Abstract session persistence interface.

    Design goals:
    - pluggable backend
    - thread-safe
    - production-ready
    - supports expiration
    - supports rotation
    - backend agnostic

    Implementations:
    - MemorySessionStore
    - SQLiteSessionStore
    - RedisSessionStore
    """

    # =====================================================
    # Core CRUD
    # =====================================================

    @abstractmethod
    def save_session(
        self,
        session: Session,
    ) -> None:
        """
        Create or overwrite session.
        """

    @abstractmethod
    def get_session(
        self,
        session_id: str,
    ) -> Session:
        """
        Fetch session by ID.

        Raises:
            SessionNotFoundError
        """

    @abstractmethod
    def update_session(
        self,
        session: Session,
    ) -> None:
        """
        Update existing session.
        """

    @abstractmethod
    def delete_session(
        self,
        session_id: str,
    ) -> None:
        """
        Remove session permanently.
        """

    # =====================================================
    # Lookup
    # =====================================================

    @abstractmethod
    def has_session(
        self,
        session_id: str,
    ) -> bool:
        """
        Fast existence check.
        """

    @abstractmethod
    def list_sessions(self) -> Iterable[Session]:
        """
        Iterate all sessions.
        """

    # =====================================================
    # Expiration / Cleanup
    # =====================================================

    @abstractmethod
    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions.

        Returns:
            number of removed sessions
        """

    # =====================================================
    # Metrics
    # =====================================================

    @abstractmethod
    def count(self) -> int:
        """
        Total active sessions.
        """

    @abstractmethod
    def clear(self) -> None:
        """
        Remove all sessions.
        """


# =========================================================
# In-Memory Base Implementation
# =========================================================

class InMemorySessionStore(BaseSessionStore):
    """
    High-performance in-memory session store.

    Features:
    - O(1) lookup
    - thread-safe
    - automatic expiration cleanup
    - bounded memory
    - production-ready locking
    """

    def __init__(
        self,
        *,
        max_sessions: int = 100_000,
        cleanup_interval_seconds: int = 60,
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

        self._sessions: Dict[str, Session] = {}

        self._lock = threading.RLock()

        self._last_cleanup_monotonic = (
            time.monotonic()
        )

    # =====================================================
    # Internal Helpers
    # =====================================================

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
    def _validate_session(
        session: Session,
    ) -> Session:

        if not isinstance(session, Session):
            raise InvalidSessionError(
                "Expected Session instance."
            )

        return session

    @staticmethod
    def _utc_now_unix() -> float:
        return time.time()

    def _should_cleanup(self) -> bool:
        elapsed = (
            time.monotonic()
            - self._last_cleanup_monotonic
        )

        return (
            elapsed >= self.cleanup_interval_seconds
        )

    def _mark_cleanup(self) -> None:
        self._last_cleanup_monotonic = (
            time.monotonic()
        )

    # =====================================================
    # CRUD
    # =====================================================

    def save_session(
        self,
        session: Session,
    ) -> None:

        session = self._validate_session(
            session
        )

        with self._lock:

            if self._should_cleanup():
                self.cleanup_expired_sessions()

            if (
                len(self._sessions)
                >= self.max_sessions
            ):
                self.cleanup_expired_sessions()

            if (
                len(self._sessions)
                >= self.max_sessions
            ):
                raise SessionStoreError(
                    "Session store capacity exceeded."
                )

            self._sessions[
                session.session_id
            ] = session

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

            if session.is_expired():
                del self._sessions[
                    session_id
                ]

                raise SessionNotFoundError(
                    f"Session expired: "
                    f"{session_id}"
                )

            return session

    def update_session(
        self,
        session: Session,
    ) -> None:

        session = self._validate_session(
            session
        )

        with self._lock:

            if (
                session.session_id
                not in self._sessions
            ):
                raise SessionNotFoundError(
                    f"Session not found: "
                    f"{session.session_id}"
                )

            self._sessions[
                session.session_id
            ] = session

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

            self._sessions.pop(
                session_id,
                None,
            )

    # =====================================================
    # Lookup
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

            if session.is_expired():
                del self._sessions[
                    session_id
                ]
                return False

            return True

    def list_sessions(
        self,
    ) -> Iterable[Session]:

        with self._lock:

            sessions = list(
                self._sessions.values()
            )

        for session in sessions:

            if session.is_expired():
                continue

            yield session

    # =====================================================
    # Cleanup
    # =====================================================

    def cleanup_expired_sessions(
        self,
    ) -> int:

        removed = 0

        now = self._utc_now_unix()

        with self._lock:

            expired_ids = []

            for (
                session_id,
                session,
            ) in self._sessions.items():

                if session.is_expired():
                    expired_ids.append(
                        session_id
                    )

            for session_id in expired_ids:

                del self._sessions[
                    session_id
                ]

                removed += 1

            self._mark_cleanup()

        return removed

    # =====================================================
    # Metrics
    # =====================================================

    def count(self) -> int:

        with self._lock:
            return len(
                self._sessions
            )

    def clear(self) -> None:

        with self._lock:
            self._sessions.clear()

    # =====================================================
    # Additional Utilities
    # =====================================================

    def list_active_sessions(
        self,
    ) -> Iterable[Session]:

        for session in self.list_sessions():

            if (
                session.status
                == SessionStatus.ACTIVE
            ):
                yield session

    def stats(self) -> dict:

        with self._lock:

            active = 0
            expired = 0
            closed = 0

            for session in (
                self._sessions.values()
            ):

                if session.is_expired():
                    expired += 1

                elif (
                    session.status
                    == SessionStatus.ACTIVE
                ):
                    active += 1

                else:
                    closed += 1

            return {
                "total_sessions": len(
                    self._sessions
                ),
                "active_sessions": active,
                "expired_sessions": expired,
                "closed_sessions": closed,
                "max_sessions": (
                    self.max_sessions
                ),
                "cleanup_interval_seconds": (
                    self.cleanup_interval_seconds
                ),
            }


__all__ = [
    "SessionStoreError",
    "SessionNotFoundError",
    "SessionAlreadyExistsError",
    "InvalidSessionError",
    "BaseSessionStore",
    "InMemorySessionStore",
]
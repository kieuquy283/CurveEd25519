from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from .session_store import (
    BaseSessionStore,
    SessionStoreError,
    SessionNotFoundError,
)

from ..core.session import (
    Session,
    SessionStatus,
)


# =========================================================
# SQLite Session Store
# =========================================================

class SQLiteSessionStore(BaseSessionStore):
    """
    Persistent SQLite-backed session store.

    Features:
    - thread-safe
    - WAL mode
    - automatic cleanup
    - session expiration
    - atomic updates
    - high read performance
    - durable storage

    Optimized for:
    - secure messaging systems
    - medium-scale desktop/server workloads
    - persistent session management
    """

    DEFAULT_CLEANUP_INTERVAL_SECONDS = 300

    def __init__(
        self,
        db_path: str = "sessions.db",
        *,
        cleanup_interval_seconds: int = (
            DEFAULT_CLEANUP_INTERVAL_SECONDS
        ),
    ) -> None:

        self.db_path = str(
            Path(db_path).expanduser().resolve()
        )

        self.cleanup_interval_seconds = (
            cleanup_interval_seconds
        )

        self._lock = threading.RLock()

        self._last_cleanup_monotonic = (
            time.monotonic()
        )

        self._initialize_database()

    # =====================================================
    # Database Initialization
    # =====================================================

    def _initialize_database(self) -> None:

        with self._connection() as conn:

            conn.execute(
                """
                PRAGMA journal_mode=WAL;
                """
            )

            conn.execute(
                """
                PRAGMA synchronous=NORMAL;
                """
            )

            conn.execute(
                """
                PRAGMA foreign_keys=ON;
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,

                    sender_id TEXT NOT NULL,
                    receiver_id TEXT NOT NULL,

                    status TEXT NOT NULL,

                    created_at_unix REAL NOT NULL,
                    updated_at_unix REAL NOT NULL,
                    expires_at_unix REAL NOT NULL,

                    root_key_b64 TEXT NOT NULL,

                    send_chain_key_b64 TEXT NOT NULL,
                    recv_chain_key_b64 TEXT NOT NULL,

                    send_counter INTEGER NOT NULL,
                    recv_counter INTEGER NOT NULL,

                    dh_ratchet_public_b64 TEXT,
                    dh_ratchet_private_b64 TEXT,

                    metadata_json TEXT
                );
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_expiry
                ON sessions(expires_at_unix);
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_status
                ON sessions(status);
                """
            )

            conn.commit()

    # =====================================================
    # Connection Management
    # =====================================================

    @contextmanager
    def _connection(self):

        conn = sqlite3.connect(
            self.db_path,
            timeout=30,
            isolation_level=None,
            check_same_thread=False,
        )

        conn.row_factory = sqlite3.Row

        try:
            yield conn

        finally:
            conn.close()

    # =====================================================
    # Time Helpers
    # =====================================================

    @staticmethod
    def utc_now_unix() -> float:

        from datetime import (
            datetime,
            timezone,
        )

        return datetime.now(
            timezone.utc
        ).timestamp()

    def _should_cleanup(self) -> bool:

        elapsed = (
            time.monotonic()
            - self._last_cleanup_monotonic
        )

        return (
            elapsed >=
            self.cleanup_interval_seconds
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

        if not isinstance(session, Session):
            raise SessionStoreError(
                "session must be Session."
            )

        with self._lock:

            if self._should_cleanup():
                self.cleanup_expired_sessions()

            with self._connection() as conn:

                conn.execute(
                    """
                    INSERT OR REPLACE INTO sessions (
                        session_id,

                        sender_id,
                        receiver_id,

                        status,

                        created_at_unix,
                        updated_at_unix,
                        expires_at_unix,

                        root_key_b64,

                        send_chain_key_b64,
                        recv_chain_key_b64,

                        send_counter,
                        recv_counter,

                        dh_ratchet_public_b64,
                        dh_ratchet_private_b64,

                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session.session_id,

                        session.sender_id,
                        session.receiver_id,

                        session.status.value,

                        session.created_at_unix,
                        session.updated_at_unix,
                        session.expires_at_unix,

                        session.root_key_b64,

                        session.send_chain_key_b64,
                        session.recv_chain_key_b64,

                        session.send_counter,
                        session.recv_counter,

                        session.dh_ratchet_public_b64,
                        session.dh_ratchet_private_b64,

                        session.metadata_json,
                    ),
                )

                conn.commit()

    def get_session(
        self,
        session_id: str,
    ) -> Session:

        with self._lock:

            with self._connection() as conn:

                row = conn.execute(
                    """
                    SELECT *
                    FROM sessions
                    WHERE session_id = ?
                    LIMIT 1
                    """,
                    (session_id,),
                ).fetchone()

                if row is None:
                    raise SessionNotFoundError(
                        f"Session not found: "
                        f"{session_id}"
                    )

                return self._row_to_session(row)

    def update_session(
        self,
        session: Session,
    ) -> None:

        session.updated_at_unix = (
            self.utc_now_unix()
        )

        self.save_session(session)

    def delete_session(
        self,
        session_id: str,
    ) -> None:

        with self._lock:

            with self._connection() as conn:

                conn.execute(
                    """
                    DELETE FROM sessions
                    WHERE session_id = ?
                    """,
                    (session_id,),
                )

                conn.commit()

    def has_session(
        self,
        session_id: str,
    ) -> bool:

        with self._lock:

            with self._connection() as conn:

                row = conn.execute(
                    """
                    SELECT 1
                    FROM sessions
                    WHERE session_id = ?
                    LIMIT 1
                    """,
                    (session_id,),
                ).fetchone()

                return row is not None

    # =====================================================
    # Expiration Cleanup
    # =====================================================

    def cleanup_expired_sessions(
        self,
    ) -> int:

        now = self.utc_now_unix()

        with self._lock:

            with self._connection() as conn:

                cursor = conn.execute(
                    """
                    DELETE FROM sessions
                    WHERE expires_at_unix <= ?
                    """,
                    (now,),
                )

                removed = cursor.rowcount

                conn.commit()

            self._mark_cleanup()

        return removed

    # =====================================================
    # Session Rotation
    # =====================================================

    def rotate_session(
        self,
        session_id: str,
        *,
        new_root_key_b64: str,
        new_send_chain_key_b64: str,
        new_recv_chain_key_b64: str,
    ) -> None:

        now = self.utc_now_unix()

        with self._lock:

            with self._connection() as conn:

                cursor = conn.execute(
                    """
                    UPDATE sessions
                    SET
                        root_key_b64 = ?,
                        send_chain_key_b64 = ?,
                        recv_chain_key_b64 = ?,
                        updated_at_unix = ?
                    WHERE session_id = ?
                    """,
                    (
                        new_root_key_b64,
                        new_send_chain_key_b64,
                        new_recv_chain_key_b64,
                        now,
                        session_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise SessionNotFoundError(
                        f"Session not found: "
                        f"{session_id}"
                    )

                conn.commit()

    # =====================================================
    # Status Management
    # =====================================================

    def set_session_status(
        self,
        session_id: str,
        status: SessionStatus,
    ) -> None:

        now = self.utc_now_unix()

        with self._lock:

            with self._connection() as conn:

                cursor = conn.execute(
                    """
                    UPDATE sessions
                    SET
                        status = ?,
                        updated_at_unix = ?
                    WHERE session_id = ?
                    """,
                    (
                        status.value,
                        now,
                        session_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise SessionNotFoundError(
                        f"Session not found: "
                        f"{session_id}"
                    )

                conn.commit()

    # =====================================================
    # Counters
    # =====================================================

    def increment_send_counter(
        self,
        session_id: str,
    ) -> int:

        return self._increment_counter(
            session_id,
            "send_counter",
        )

    def increment_recv_counter(
        self,
        session_id: str,
    ) -> int:

        return self._increment_counter(
            session_id,
            "recv_counter",
        )

    def _increment_counter(
        self,
        session_id: str,
        field: str,
    ) -> int:

        with self._lock:

            with self._connection() as conn:

                conn.execute("BEGIN IMMEDIATE")

                row = conn.execute(
                    f"""
                    SELECT {field}
                    FROM sessions
                    WHERE session_id = ?
                    """,
                    (session_id,),
                ).fetchone()

                if row is None:
                    raise SessionNotFoundError(
                        f"Session not found: "
                        f"{session_id}"
                    )

                value = row[field] + 1

                conn.execute(
                    f"""
                    UPDATE sessions
                    SET
                        {field} = ?,
                        updated_at_unix = ?
                    WHERE session_id = ?
                    """,
                    (
                        value,
                        self.utc_now_unix(),
                        session_id,
                    ),
                )

                conn.commit()

                return value

    # =====================================================
    # Metrics
    # =====================================================

    def session_count(self) -> int:

        with self._connection() as conn:

            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM sessions
                """
            ).fetchone()

            return int(row["count"])

    # Compatibility helpers for BaseSessionStore
    def count(self) -> int:
        return self.session_count()

    def list_sessions(self):
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM sessions
                """
            ).fetchall()

            return [
                self._row_to_session(row)
                for row in rows
            ]

    def clear(self) -> None:
        with self._lock:
            with self._connection() as conn:
                conn.execute(
                    """
                    DELETE FROM sessions
                    """
                )
                conn.commit()

    def active_session_count(self) -> int:

        with self._connection() as conn:

            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM sessions
                WHERE status = ?
                """,
                (
                    SessionStatus.ACTIVE.value,
                ),
            ).fetchone()

            return int(row["count"])

    # =====================================================
    # Serialization
    # =====================================================

    @staticmethod
    def _row_to_session(
        row: sqlite3.Row,
    ) -> Session:

        return Session(
            session_id=row["session_id"],

            sender_id=row["sender_id"],
            receiver_id=row["receiver_id"],

            status=SessionStatus(
                row["status"]
            ),

            created_at_unix=row[
                "created_at_unix"
            ],

            updated_at_unix=row[
                "updated_at_unix"
            ],

            expires_at_unix=row[
                "expires_at_unix"
            ],

            root_key_b64=row[
                "root_key_b64"
            ],

            send_chain_key_b64=row[
                "send_chain_key_b64"
            ],

            recv_chain_key_b64=row[
                "recv_chain_key_b64"
            ],

            send_counter=row[
                "send_counter"
            ],

            recv_counter=row[
                "recv_counter"
            ],

            dh_ratchet_public_b64=row[
                "dh_ratchet_public_b64"
            ],

            dh_ratchet_private_b64=row[
                "dh_ratchet_private_b64"
            ],

            metadata_json=row[
                "metadata_json"
            ],
        )
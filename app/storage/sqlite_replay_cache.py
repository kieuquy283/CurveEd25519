from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Final

from .base_replay_cache import (
    BaseReplayCache,
    ReplayCacheError,
)

from .replay_record import (
    ReplayCacheRecord,
)


DEFAULT_DB_FILENAME: Final[str] = (
    "replay_cache.db"
)

DEFAULT_BUSY_TIMEOUT_MS: Final[int] = 5_000


class SQLiteReplayCacheError(
    ReplayCacheError
):
    """SQLite replay cache error."""


class SQLiteReplayCache(
    BaseReplayCache
):
    """
    Persistent replay cache using SQLite.

    Features:
    ---------
    - persistent replay protection
    - survives app restart
    - thread-safe
    - atomic inserts
    - WAL mode
    - automatic cleanup
    - indexed lookups

    Schema:
    -------
        replay_records(
            replay_key TEXT PRIMARY KEY,
            created_at_unix REAL,
            expires_at_unix REAL,
            message_id TEXT,
            sender_fingerprint TEXT
        )
    """

    def __init__(
        self,
        *,
        db_path: str | Path = DEFAULT_DB_FILENAME,
        auto_cleanup: bool = True,
        cleanup_interval_seconds: int = 60,
    ) -> None:

        self.db_path = str(db_path)

        self.auto_cleanup = auto_cleanup

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

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=(
                DEFAULT_BUSY_TIMEOUT_MS / 1000
            ),
            check_same_thread=False,
        )

        conn.row_factory = sqlite3.Row

        return conn

    def _initialize_database(
        self,
    ) -> None:

        with self._connect() as conn:

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
                CREATE TABLE IF NOT EXISTS replay_records (
                    replay_key TEXT PRIMARY KEY,
                    created_at_unix REAL NOT NULL,
                    expires_at_unix REAL NOT NULL,
                    message_id TEXT NOT NULL,
                    sender_fingerprint TEXT
                );
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_replay_expires
                ON replay_records(
                    expires_at_unix
                );
                """
            )

            conn.commit()

    # =====================================================
    # Time Helpers
    # =====================================================

    @staticmethod
    def utc_now_unix() -> float:
        return time.time()

    def _should_cleanup(self) -> bool:

        elapsed = (
            time.monotonic()
            - self._last_cleanup_monotonic
        )

        return (
            elapsed
            >= self.cleanup_interval_seconds
        )

    def _mark_cleanup(self) -> None:
        self._last_cleanup_monotonic = (
            time.monotonic()
        )

    # =====================================================
    # Validation
    # =====================================================

    @staticmethod
    def _validate_replay_key(
        replay_key: str,
    ) -> str:

        if not isinstance(
            replay_key,
            str,
        ):
            raise SQLiteReplayCacheError(
                "replay_key must be string."
            )

        replay_key = replay_key.strip()

        if not replay_key:
            raise SQLiteReplayCacheError(
                "replay_key cannot be empty."
            )

        return replay_key

    # =====================================================
    # Core Operations
    # =====================================================

    def has(
        self,
        replay_key: str,
    ) -> bool:

        replay_key = (
            self._validate_replay_key(
                replay_key
            )
        )

        if (
            self.auto_cleanup
            and self._should_cleanup()
        ):
            self.cleanup()

        with self._lock:

            with self._connect() as conn:

                cursor = conn.execute(
                    """
                    SELECT 1
                    FROM replay_records
                    WHERE replay_key = ?
                    LIMIT 1
                    """,
                    (replay_key,),
                )

                row = cursor.fetchone()

                return row is not None

    def put(
        self,
        record: ReplayCacheRecord,
    ) -> None:

        if not isinstance(
            record,
            ReplayCacheRecord,
        ):
            raise SQLiteReplayCacheError(
                "record must be ReplayCacheRecord."
            )

        if (
            self.auto_cleanup
            and self._should_cleanup()
        ):
            self.cleanup()

        with self._lock:

            try:

                with self._connect() as conn:

                    conn.execute(
                        """
                        INSERT INTO replay_records (
                            replay_key,
                            created_at_unix,
                            expires_at_unix,
                            message_id,
                            sender_fingerprint
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            record.replay_key,
                            record.created_at_unix,
                            record.expires_at_unix,
                            record.message_id,
                            record.sender_fingerprint,
                        ),
                    )

                    conn.commit()

            except sqlite3.IntegrityError as exc:
                raise SQLiteReplayCacheError(
                    f"Replay key already exists: "
                    f"{record.replay_key}"
                ) from exc

    def remove(
        self,
        replay_key: str,
    ) -> None:

        replay_key = (
            self._validate_replay_key(
                replay_key
            )
        )

        with self._lock:

            with self._connect() as conn:

                conn.execute(
                    """
                    DELETE FROM replay_records
                    WHERE replay_key = ?
                    """,
                    (replay_key,),
                )

                conn.commit()

    # =====================================================
    # Cleanup
    # =====================================================

    def cleanup(self) -> int:
        """
        Remove expired replay records.

        Returns:
            number of deleted rows
        """

        now = self.utc_now_unix()

        with self._lock:

            with self._connect() as conn:

                cursor = conn.execute(
                    """
                    DELETE FROM replay_records
                    WHERE expires_at_unix <= ?
                    """,
                    (now,),
                )

                deleted = cursor.rowcount

                conn.commit()

            self._mark_cleanup()

            return deleted

    # =====================================================
    # Utilities
    # =====================================================

    def clear(self) -> None:

        with self._lock:

            with self._connect() as conn:

                conn.execute(
                    """
                    DELETE FROM replay_records
                    """
                )

                conn.commit()

    def size(self) -> int:

        with self._lock:

            with self._connect() as conn:

                cursor = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM replay_records
                    """
                )

                row = cursor.fetchone()

                return int(row[0])

    def is_empty(self) -> bool:
        return self.size() == 0

    # =====================================================
    # Metrics / Debug
    # =====================================================

    def stats(self) -> dict:

        return {
            "backend": "sqlite",
            "db_path": self.db_path,
            "records": self.size(),
            "auto_cleanup": (
                self.auto_cleanup
            ),
            "cleanup_interval_seconds": (
                self.cleanup_interval_seconds
            ),
        }

    def export_state(self) -> dict:

        with self._lock:

            with self._connect() as conn:

                cursor = conn.execute(
                    """
                    SELECT
                        replay_key,
                        created_at_unix,
                        expires_at_unix,
                        message_id,
                        sender_fingerprint
                    FROM replay_records
                    """
                )

                rows = cursor.fetchall()

                result = {}

                for row in rows:

                    result[
                        row["replay_key"]
                    ] = {
                        "created_at_unix": (
                            row[
                                "created_at_unix"
                            ]
                        ),
                        "expires_at_unix": (
                            row[
                                "expires_at_unix"
                            ]
                        ),
                        "message_id": (
                            row["message_id"]
                        ),
                        "sender_fingerprint": (
                            row[
                                "sender_fingerprint"
                            ]
                        ),
                    }

                return result


__all__ = [
    "SQLiteReplayCacheError",
    "SQLiteReplayCache",
]
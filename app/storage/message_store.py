from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import List, Optional

from models.message_record import (
    MessageDirection,
    MessageRecord,
    MessageStatus,
)


# =========================================================
# Exceptions
# =========================================================

class MessageStoreError(Exception):
    """Base message store exception."""


class MessageNotFoundError(MessageStoreError):
    """Message not found."""


# =========================================================
# Message Store
# =========================================================

class MessageStore:
    """
    Persistent SQLite message storage.

    Responsibilities:
    - store encrypted message metadata
    - inbox / outbox queries
    - message status updates
    - attachment metadata persistence
    - local chat history

    DOES NOT:
    - encrypt/decrypt payloads
    - replay protection
    - protocol orchestration
    """

    def __init__(
        self,
        db_path: str = "data/messages.db",
    ) -> None:

        self.db_path = db_path

        Path(db_path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = threading.RLock()

        self._init_db()

    # =====================================================
    # Database
    # =====================================================

    def _connect(self) -> sqlite3.Connection:

        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
        )

        conn.row_factory = sqlite3.Row

        return conn

    def _init_db(self) -> None:

        with self._connect() as conn:

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,

                    session_id TEXT,
                    sender TEXT NOT NULL,
                    receiver TEXT NOT NULL,

                    direction TEXT NOT NULL,
                    status TEXT NOT NULL,

                    ciphertext_b64 TEXT,
                    plaintext_preview TEXT,

                    envelope_json TEXT,

                    attachment_id TEXT,

                    created_at TEXT NOT NULL,
                    received_at TEXT,

                    verified INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id)
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_sender_receiver
                ON messages(sender, receiver)
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_created_at
                ON messages(created_at)
                """
            )

            conn.commit()

    # =====================================================
    # Insert
    # =====================================================

    def save_message(
        self,
        record: MessageRecord,
    ) -> None:

        with self._lock:

            with self._connect() as conn:

                conn.execute(
                    """
                    INSERT OR REPLACE INTO messages (
                        message_id,
                        session_id,
                        sender,
                        receiver,
                        direction,
                        status,
                        ciphertext_b64,
                        plaintext_preview,
                        envelope_json,
                        attachment_id,
                        created_at,
                        received_at,
                        verified
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.message_id,
                        record.session_id,
                        record.sender,
                        record.receiver,
                        record.direction.value,
                        record.status.value,
                        record.ciphertext_b64,
                        record.plaintext_preview,
                        record.envelope_json,
                        record.attachment_id,
                        record.created_at,
                        record.received_at,
                        int(record.verified),
                    ),
                )

                conn.commit()

    # =====================================================
    # Queries
    # =====================================================

    def get_message(
        self,
        message_id: str,
    ) -> MessageRecord:

        with self._lock:

            with self._connect() as conn:

                row = conn.execute(
                    """
                    SELECT *
                    FROM messages
                    WHERE message_id = ?
                    """,
                    (message_id,),
                ).fetchone()

                if row is None:
                    raise MessageNotFoundError(
                        f"Message not found: {message_id}"
                    )

                return self._row_to_record(row)

    def list_messages(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MessageRecord]:

        with self._lock:

            with self._connect() as conn:

                rows = conn.execute(
                    """
                    SELECT *
                    FROM messages
                    ORDER BY created_at DESC
                    LIMIT ?
                    OFFSET ?
                    """,
                    (limit, offset),
                ).fetchall()

                return [
                    self._row_to_record(row)
                    for row in rows
                ]

    def get_conversation(
        self,
        *,
        user_a: str,
        user_b: str,
        limit: int = 100,
    ) -> List[MessageRecord]:

        with self._lock:

            with self._connect() as conn:

                rows = conn.execute(
                    """
                    SELECT *
                    FROM messages
                    WHERE
                        (sender = ? AND receiver = ?)
                        OR
                        (sender = ? AND receiver = ?)
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (
                        user_a,
                        user_b,
                        user_b,
                        user_a,
                        limit,
                    ),
                ).fetchall()

                return [
                    self._row_to_record(row)
                    for row in rows
                ]

    def get_session_messages(
        self,
        session_id: str,
    ) -> List[MessageRecord]:

        with self._lock:

            with self._connect() as conn:

                rows = conn.execute(
                    """
                    SELECT *
                    FROM messages
                    WHERE session_id = ?
                    ORDER BY created_at ASC
                    """,
                    (session_id,),
                ).fetchall()

                return [
                    self._row_to_record(row)
                    for row in rows
                ]

    # =====================================================
    # Status Updates
    # =====================================================

    def update_status(
        self,
        *,
        message_id: str,
        status: MessageStatus,
    ) -> None:

        with self._lock:

            with self._connect() as conn:

                cursor = conn.execute(
                    """
                    UPDATE messages
                    SET status = ?
                    WHERE message_id = ?
                    """,
                    (
                        status.value,
                        message_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise MessageNotFoundError(
                        f"Message not found: {message_id}"
                    )

                conn.commit()

    def mark_verified(
        self,
        *,
        message_id: str,
        verified: bool = True,
    ) -> None:

        with self._lock:

            with self._connect() as conn:

                cursor = conn.execute(
                    """
                    UPDATE messages
                    SET verified = ?
                    WHERE message_id = ?
                    """,
                    (
                        int(verified),
                        message_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise MessageNotFoundError(
                        f"Message not found: {message_id}"
                    )

                conn.commit()

    # =====================================================
    # Delete
    # =====================================================

    def delete_message(
        self,
        message_id: str,
    ) -> None:

        with self._lock:

            with self._connect() as conn:

                cursor = conn.execute(
                    """
                    DELETE FROM messages
                    WHERE message_id = ?
                    """,
                    (message_id,),
                )

                if cursor.rowcount == 0:
                    raise MessageNotFoundError(
                        f"Message not found: {message_id}"
                    )

                conn.commit()

    def clear_all(self) -> None:

        with self._lock:

            with self._connect() as conn:

                conn.execute(
                    "DELETE FROM messages"
                )

                conn.commit()

    # =====================================================
    # Metrics
    # =====================================================

    def count(self) -> int:

        with self._lock:

            with self._connect() as conn:

                row = conn.execute(
                    """
                    SELECT COUNT(*) as total
                    FROM messages
                    """
                ).fetchone()

                return int(row["total"])

    # =====================================================
    # Internal
    # =====================================================

    @staticmethod
    def _row_to_record(
        row: sqlite3.Row,
    ) -> MessageRecord:

        return MessageRecord(
            message_id=row["message_id"],

            session_id=row["session_id"],

            sender=row["sender"],
            receiver=row["receiver"],

            direction=MessageDirection(
                row["direction"]
            ),

            status=MessageStatus(
                row["status"]
            ),

            ciphertext_b64=row["ciphertext_b64"],

            plaintext_preview=row[
                "plaintext_preview"
            ],

            envelope_json=row[
                "envelope_json"
            ],

            attachment_id=row[
                "attachment_id"
            ],

            created_at=row["created_at"],

            received_at=row[
                "received_at"
            ],

            verified=bool(
                row["verified"]
            ),
        )
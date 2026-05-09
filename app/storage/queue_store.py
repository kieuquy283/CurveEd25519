from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import List, Optional

from app.models.delivery_record import (
    DeliveryRecord,
    DeliveryState,
)


# =========================================================
# Exceptions
# =========================================================

class QueueStoreError(Exception):
    """Base queue store exception."""


class QueueRecordNotFoundError(
    QueueStoreError
):
    """Queue record not found."""


# =========================================================
# Queue Store
# =========================================================

class QueueStore:
    """
    Persistent delivery queue storage.

    Responsibilities:
    - persist outbound queue
    - retry scheduling
    - dead-letter handling
    - ACK persistence
    - offline recovery

    Backend:
        SQLite
    """

    def __init__(
        self,
        db_path: str = (
            "data/delivery_queue.db"
        ),
    ) -> None:

        self.db_path = db_path

        Path(db_path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = threading.RLock()

        self._init_db()

    # =====================================================
    # DB
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
                CREATE TABLE IF NOT EXISTS delivery_queue (

                    message_id TEXT PRIMARY KEY,

                    sender_id TEXT NOT NULL,
                    receiver_id TEXT NOT NULL,

                    session_id TEXT,
                    conversation_id TEXT,

                    state TEXT NOT NULL,
                    priority TEXT NOT NULL,

                    encrypted_envelope_json TEXT,

                    plaintext_preview TEXT,

                    attachment_id TEXT,
                    attachment_count INTEGER NOT NULL DEFAULT 0,

                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 5,

                    retry_backoff_seconds INTEGER NOT NULL DEFAULT 1,

                    next_retry_at TEXT,

                    last_error TEXT,

                    ack_required INTEGER NOT NULL DEFAULT 1,
                    ack_received INTEGER NOT NULL DEFAULT 0,
                    ack_message_id TEXT,

                    delivered_at TEXT,
                    read_at TEXT,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    queued_at TEXT NOT NULL,

                    sent_at TEXT,
                    failed_at TEXT,

                    processing_time_ms INTEGER,
                    transport_latency_ms INTEGER,

                    is_offline_queued INTEGER NOT NULL DEFAULT 0,
                    is_duplicate INTEGER NOT NULL DEFAULT 0,
                    is_replayed INTEGER NOT NULL DEFAULT 0,
                    is_expired INTEGER NOT NULL DEFAULT 0,

                    ratchet_key_id TEXT,
                    replay_key TEXT,
                    nonce_id TEXT,

                    metadata_json TEXT
                )
                """
            )

            # ---------------------------------------------
            # Indexes
            # ---------------------------------------------

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_queue_state
                ON delivery_queue(state)
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_queue_next_retry
                ON delivery_queue(next_retry_at)
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_queue_receiver
                ON delivery_queue(receiver_id)
                """
            )

            conn.commit()

    # =====================================================
    # Insert
    # =====================================================

    def save(
        self,
        record: DeliveryRecord,
    ) -> None:

        with self._lock:

            with self._connect() as conn:

                conn.execute(
                    """
                    INSERT OR REPLACE INTO delivery_queue (

                        message_id,

                        sender_id,
                        receiver_id,

                        session_id,
                        conversation_id,

                        state,
                        priority,

                        encrypted_envelope_json,

                        plaintext_preview,

                        attachment_id,
                        attachment_count,

                        retry_count,
                        max_retries,

                        retry_backoff_seconds,

                        next_retry_at,

                        last_error,

                        ack_required,
                        ack_received,
                        ack_message_id,

                        delivered_at,
                        read_at,

                        created_at,
                        updated_at,
                        queued_at,

                        sent_at,
                        failed_at,

                        processing_time_ms,
                        transport_latency_ms,

                        is_offline_queued,
                        is_duplicate,
                        is_replayed,
                        is_expired,

                        ratchet_key_id,
                        replay_key,
                        nonce_id,

                        metadata_json

                    ) VALUES (

                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        record.message_id,

                        record.sender_id,
                        record.receiver_id,

                        record.session_id,
                        record.conversation_id,

                        record.state.value,
                        record.priority.value,

                        record.encrypted_envelope_json,

                        record.plaintext_preview,

                        record.attachment_id,
                        record.attachment_count,

                        record.retry_count,
                        record.max_retries,

                        record.retry_backoff_seconds,

                        record.next_retry_at,

                        record.last_error,

                        int(record.ack_required),
                        int(record.ack_received),
                        record.ack_message_id,

                        record.delivered_at,
                        record.read_at,

                        record.created_at,
                        record.updated_at,
                        record.queued_at,

                        record.sent_at,
                        record.failed_at,

                        record.processing_time_ms,
                        record.transport_latency_ms,

                        int(
                            record.is_offline_queued
                        ),

                        int(
                            record.is_duplicate
                        ),

                        int(
                            record.is_replayed
                        ),

                        int(
                            record.is_expired
                        ),

                        record.ratchet_key_id,
                        record.replay_key,
                        record.nonce_id,

                        json.dumps(
                            record.metadata
                        ),
                    ),
                )

                conn.commit()

    # =====================================================
    # Queries
    # =====================================================

    def get(
        self,
        message_id: str,
    ) -> DeliveryRecord:

        with self._lock:

            with self._connect() as conn:

                row = conn.execute(
                    """
                    SELECT *
                    FROM delivery_queue
                    WHERE message_id = ?
                    """,
                    (message_id,),
                ).fetchone()

                if row is None:
                    raise QueueRecordNotFoundError(
                        f"Queue record not found: "
                        f"{message_id}"
                    )

                return self._row_to_record(
                    row
                )

    def exists(
        self,
        message_id: str,
    ) -> bool:

        with self._lock:

            with self._connect() as conn:

                row = conn.execute(
                    """
                    SELECT 1
                    FROM delivery_queue
                    WHERE message_id = ?
                    LIMIT 1
                    """,
                    (message_id,),
                ).fetchone()

                return row is not None

    def delete(
        self,
        message_id: str,
    ) -> None:

        with self._lock:

            with self._connect() as conn:

                cursor = conn.execute(
                    """
                    DELETE FROM delivery_queue
                    WHERE message_id = ?
                    """,
                    (message_id,),
                )

                if cursor.rowcount == 0:
                    raise QueueRecordNotFoundError(
                        f"Queue record not found: "
                        f"{message_id}"
                    )

                conn.commit()

    # =====================================================
    # Queue Fetching
    # =====================================================

    def get_pending_messages(
        self,
        limit: int = 100,
    ) -> List[DeliveryRecord]:

        pending_states = (
            DeliveryState.QUEUED.value,
            DeliveryState.ENCRYPTING.value,
            DeliveryState.ENCRYPTED.value,
            DeliveryState.SENDING.value,
            DeliveryState.RETRY_PENDING.value,
        )

        placeholders = ",".join(
            "?"
            for _ in pending_states
        )

        with self._lock:

            with self._connect() as conn:

                rows = conn.execute(
                    f"""
                    SELECT *
                    FROM delivery_queue
                    WHERE state IN (
                        {placeholders}
                    )
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (
                        *pending_states,
                        limit,
                    ),
                ).fetchall()

                return [
                    self._row_to_record(row)
                    for row in rows
                ]

    def get_retry_ready_messages(
        self,
        current_time_iso: str,
        limit: int = 100,
    ) -> List[DeliveryRecord]:

        with self._lock:

            with self._connect() as conn:

                rows = conn.execute(
                    """
                    SELECT *
                    FROM delivery_queue
                    WHERE
                        state = ?
                        AND next_retry_at <= ?
                    ORDER BY next_retry_at ASC
                    LIMIT ?
                    """,
                    (
                        DeliveryState
                        .RETRY_PENDING.value,

                        current_time_iso,

                        limit,
                    ),
                ).fetchall()

                return [
                    self._row_to_record(row)
                    for row in rows
                ]

    def get_dead_letters(
        self,
    ) -> List[DeliveryRecord]:

        with self._lock:

            with self._connect() as conn:

                rows = conn.execute(
                    """
                    SELECT *
                    FROM delivery_queue
                    WHERE state = ?
                    ORDER BY updated_at DESC
                    """,
                    (
                        DeliveryState
                        .DEAD_LETTER.value,
                    ),
                ).fetchall()

                return [
                    self._row_to_record(row)
                    for row in rows
                ]

    # =====================================================
    # State Updates
    # =====================================================

    def update_state(
        self,
        *,
        message_id: str,
        state: DeliveryState,
    ) -> None:

        with self._lock:

            with self._connect() as conn:

                cursor = conn.execute(
                    """
                    UPDATE delivery_queue
                    SET
                        state = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE message_id = ?
                    """,
                    (
                        state.value,
                        message_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise QueueRecordNotFoundError(
                        f"Queue record not found: "
                        f"{message_id}"
                    )

                conn.commit()

    def mark_ack_received(
        self,
        *,
        message_id: str,
        ack_message_id: str,
        delivered_at: str,
    ) -> None:

        with self._lock:

            with self._connect() as conn:

                cursor = conn.execute(
                    """
                    UPDATE delivery_queue
                    SET
                        ack_received = 1,
                        ack_message_id = ?,
                        delivered_at = ?,
                        state = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE message_id = ?
                    """,
                    (
                        ack_message_id,
                        delivered_at,
                        DeliveryState
                        .DELIVERED.value,
                        message_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise QueueRecordNotFoundError(
                        f"Queue record not found: "
                        f"{message_id}"
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
                    SELECT COUNT(*) AS total
                    FROM delivery_queue
                    """
                ).fetchone()

                return int(
                    row["total"]
                )

    def clear(self) -> None:

        with self._lock:

            with self._connect() as conn:

                conn.execute(
                    """
                    DELETE FROM delivery_queue
                    """
                )

                conn.commit()

    # =====================================================
    # Internal
    # =====================================================

    @staticmethod
    def _row_to_record(
        row: sqlite3.Row,
    ) -> DeliveryRecord:

        metadata = {}

        if row["metadata_json"]:

            try:
                metadata = json.loads(
                    row["metadata_json"]
                )

            except Exception:
                metadata = {}

        return DeliveryRecord.from_dict(
            {
                "message_id":
                    row["message_id"],

                "sender_id":
                    row["sender_id"],

                "receiver_id":
                    row["receiver_id"],

                "session_id":
                    row["session_id"],

                "conversation_id":
                    row["conversation_id"],

                "state":
                    row["state"],

                "priority":
                    row["priority"],

                "encrypted_envelope_json":
                    row[
                        "encrypted_envelope_json"
                    ],

                "plaintext_preview":
                    row[
                        "plaintext_preview"
                    ],

                "attachment_id":
                    row["attachment_id"],

                "attachment_count":
                    row[
                        "attachment_count"
                    ],

                "retry_count":
                    row["retry_count"],

                "max_retries":
                    row["max_retries"],

                "retry_backoff_seconds":
                    row[
                        "retry_backoff_seconds"
                    ],

                "next_retry_at":
                    row["next_retry_at"],

                "last_error":
                    row["last_error"],

                "ack_required":
                    bool(
                        row[
                            "ack_required"
                        ]
                    ),

                "ack_received":
                    bool(
                        row[
                            "ack_received"
                        ]
                    ),

                "ack_message_id":
                    row[
                        "ack_message_id"
                    ],

                "delivered_at":
                    row[
                        "delivered_at"
                    ],

                "read_at":
                    row["read_at"],

                "created_at":
                    row["created_at"],

                "updated_at":
                    row["updated_at"],

                "queued_at":
                    row["queued_at"],

                "sent_at":
                    row["sent_at"],

                "failed_at":
                    row["failed_at"],

                "processing_time_ms":
                    row[
                        "processing_time_ms"
                    ],

                "transport_latency_ms":
                    row[
                        "transport_latency_ms"
                    ],

                "is_offline_queued":
                    bool(
                        row[
                            "is_offline_queued"
                        ]
                    ),

                "is_duplicate":
                    bool(
                        row[
                            "is_duplicate"
                        ]
                    ),

                "is_replayed":
                    bool(
                        row[
                            "is_replayed"
                        ]
                    ),

                "is_expired":
                    bool(
                        row[
                            "is_expired"
                        ]
                    ),

                "ratchet_key_id":
                    row[
                        "ratchet_key_id"
                    ],

                "replay_key":
                    row["replay_key"],

                "nonce_id":
                    row["nonce_id"],

                "metadata":
                    metadata,
            }
        )
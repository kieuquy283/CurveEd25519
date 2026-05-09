from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from models.delivery_record import (
    DeliveryPriority,
    DeliveryRecord,
    DeliveryState,
)

from storage.queue_store import (
    QueueStore,
    QueueRecordNotFoundError,
)

from services.protocol_service import (
    ProtocolService,
    ProtocolServiceError,
)

from services.session_service import (
    SessionService,
)

from services.ratchet_service import (
    RatchetService,
)


# =========================================================
# Exceptions
# =========================================================

class QueueServiceError(Exception):
    """Base queue service exception."""


class QueueDeliveryError(
    QueueServiceError
):
    """Message delivery failed."""


class QueueRetryExceededError(
    QueueServiceError
):
    """Retry limit exceeded."""


# =========================================================
# Queue Service
# =========================================================

class QueueService:
    """
    Reliable outbound delivery queue.

    Responsibilities:
    - outbound persistence
    - retry scheduling
    - ACK handling
    - dead-letter queue
    - exponential backoff
    - offline-safe delivery
    - resend orchestration

    DOES NOT:
    - transport networking
    - websocket implementation
    - UI rendering
    """

    DEFAULT_MAX_RETRIES = 5

    BASE_BACKOFF_SECONDS = 2

    MAX_BACKOFF_SECONDS = 300

    PROCESS_LOOP_INTERVAL = 1.0

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        queue_store: Optional[
            QueueStore
        ] = None,

        protocol_service: Optional[
            ProtocolService
        ] = None,

        session_service: Optional[
            SessionService
        ] = None,

        ratchet_service: Optional[
            RatchetService
        ] = None,
    ) -> None:

        self.queue_store = (
            queue_store
            or QueueStore()
        )

        self.protocol_service = (
            protocol_service
            or ProtocolService()
        )

        self.session_service = (
            session_service
            or SessionService()
        )

        self.ratchet_service = (
            ratchet_service
            or RatchetService()
        )

        self._running = False

        self._worker_thread: (
            threading.Thread | None
        ) = None

        self._lock = threading.RLock()

    # =====================================================
    # Queue Lifecycle
    # =====================================================

    def start(self) -> None:

        with self._lock:

            if self._running:
                return

            self._running = True

            self._worker_thread = (
                threading.Thread(
                    target=self._worker_loop,
                    daemon=True,
                )
            )

            self._worker_thread.start()

    def stop(self) -> None:

        with self._lock:

            self._running = False

    # =====================================================
    # Public API
    # =====================================================

    def enqueue_message(
        self,
        *,
        sender_profile: dict,
        receiver_contact: dict,
        plaintext: str | bytes,
        priority: DeliveryPriority = (
            DeliveryPriority.NORMAL
        ),
        metadata: Optional[dict] = None,
    ) -> DeliveryRecord:
        """
        Queue outbound message.
        """

        now = self._utc_now_iso()

        # ================================================
        # Encrypt immediately
        # ================================================

        protocol_result = (
            self.protocol_service.send_message(
                sender_profile=sender_profile,
                receiver_contact=receiver_contact,
                plaintext=plaintext,
            )
        )

        envelope = protocol_result[
            "envelope"
        ]

        message_id = envelope[
            "header"
        ]["message_id"]

        record = DeliveryRecord(
            message_id=message_id,

            sender_id=str(
                sender_profile.get("name")
            ),

            receiver_id=str(
                receiver_contact.get("name")
            ),

            session_id=(
                self._safe_session_id(
                    sender_profile,
                    receiver_contact,
                )
            ),

            state=DeliveryState.QUEUED,

            priority=priority,

            encrypted_envelope_json=(
                self._json_dumps(
                    envelope
                )
            ),

            plaintext_preview=(
                self._preview(
                    plaintext
                )
            ),

            retry_count=0,

            max_retries=(
                self.DEFAULT_MAX_RETRIES
            ),

            retry_backoff_seconds=(
                self.BASE_BACKOFF_SECONDS
            ),

            queued_at=now,
            created_at=now,
            updated_at=now,

            metadata=metadata or {},
        )

        self.queue_store.save(record)

        return record

    # =====================================================
    # Processing
    # =====================================================

    def process_queue_once(
        self,
    ) -> int:
        """
        Process:
        - queued messages
        - retryable messages
        """

        processed = 0

        # ================================================
        # New messages
        # ================================================

        pending = (
            self.queue_store
            .get_pending_messages()
        )

        for record in pending:

            try:

                self._deliver_record(
                    record
                )

                processed += 1

            except Exception:
                continue

        # ================================================
        # Retry messages
        # ================================================

        retry_ready = (
            self.queue_store
            .get_retry_ready_messages(
                current_time_iso=(
                    self._utc_now_iso()
                )
            )
        )

        for record in retry_ready:

            try:

                self._deliver_record(
                    record
                )

                processed += 1

            except Exception:
                continue

        return processed

    # =====================================================
    # ACK Handling
    # =====================================================

    def acknowledge_delivery(
        self,
        *,
        message_id: str,
        ack_message_id: str,
    ) -> None:
        """
        Mark delivery ACK received.
        """

        self.queue_store.mark_ack_received(
            message_id=message_id,

            ack_message_id=(
                ack_message_id
            ),

            delivered_at=(
                self._utc_now_iso()
            ),
        )

    # =====================================================
    # Delivery Logic
    # =====================================================

    def _deliver_record(
        self,
        record: DeliveryRecord,
    ) -> None:

        # ================================================
        # Already delivered
        # ================================================

        if record.ack_received:
            return

        # ================================================
        # Max retries exceeded
        # ================================================

        if (
            record.retry_count
            >= record.max_retries
        ):

            self.queue_store.update_state(
                message_id=record.message_id,
                state=(
                    DeliveryState
                    .DEAD_LETTER
                ),
            )

            raise (
                QueueRetryExceededError(
                    f"Retry exceeded: "
                    f"{record.message_id}"
                )
            )

        # ================================================
        # Sending state
        # ================================================

        self.queue_store.update_state(
            message_id=record.message_id,
            state=DeliveryState.SENDING,
        )

        try:

            # ============================================
            # Transport hook
            # ============================================

            self._simulate_transport_send(
                record
            )

            self.queue_store.update_state(
                message_id=record.message_id,
                state=(
                    DeliveryState.SENT
                ),
            )

        except Exception as exc:

            self._schedule_retry(
                record=record,
                error=str(exc),
            )

            raise QueueDeliveryError(
                str(exc)
            ) from exc

    # =====================================================
    # Retry Logic
    # =====================================================

    def _schedule_retry(
        self,
        *,
        record: DeliveryRecord,
        error: str,
    ) -> None:

        retry_count = (
            record.retry_count + 1
        )

        backoff = min(
            (
                self.BASE_BACKOFF_SECONDS
                * (
                    2
                    ** retry_count
                )
            ),
            self.MAX_BACKOFF_SECONDS,
        )

        next_retry = (
            datetime.now(
                timezone.utc
            )
            + timedelta(
                seconds=backoff
            )
        )

        updated = record.copy_with(
            state=(
                DeliveryState
                .RETRY_PENDING
            ),

            retry_count=retry_count,

            retry_backoff_seconds=(
                backoff
            ),

            next_retry_at=(
                next_retry.isoformat()
            ),

            last_error=error,

            updated_at=(
                self._utc_now_iso()
            ),
        )

        self.queue_store.save(
            updated
        )

    # =====================================================
    # Worker Loop
    # =====================================================

    def _worker_loop(
        self,
    ) -> None:

        while self._running:

            try:
                self.process_queue_once()

            except Exception:
                pass

            time.sleep(
                self.PROCESS_LOOP_INTERVAL
            )

    # =====================================================
    # Transport Hook
    # =====================================================

    def _simulate_transport_send(
        self,
        record: DeliveryRecord,
    ) -> None:
        """
        Placeholder transport layer.

        Replace later with:
        - websocket transport
        - tcp transport
        - http transport
        """

        time.sleep(0.05)

    # =====================================================
    # Utilities
    # =====================================================

    @staticmethod
    def _utc_now_iso() -> str:

        return (
            datetime.now(
                timezone.utc
            )
            .replace(
                microsecond=0
            )
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            )
        )

    @staticmethod
    def _preview(
        plaintext: str | bytes,
        limit: int = 64,
    ) -> str:

        if isinstance(
            plaintext,
            bytes,
        ):

            try:
                plaintext = (
                    plaintext.decode(
                        "utf-8"
                    )
                )

            except Exception:
                return "<binary>"

        plaintext = plaintext.strip()

        if len(plaintext) <= limit:
            return plaintext

        return (
            plaintext[:limit]
            + "..."
        )

    @staticmethod
    def _json_dumps(
        obj: dict,
    ) -> str:

        import json

        return json.dumps(
            obj,
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _safe_session_id(
        sender_profile: dict,
        receiver_contact: dict,
    ) -> str:

        sender = str(
            sender_profile.get("name")
        )

        receiver = str(
            receiver_contact.get("name")
        )

        ordered = sorted(
            [sender, receiver]
        )

        return (
            f"{ordered[0]}:"
            f"{ordered[1]}"
        )
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from models.delivery_record import (
    DeliveryRecord,
    DeliveryState,
)

from storage.queue_store import (
    QueueStore,
)

from services.delivery_service import (
    DeliveryService,
)


# =========================================================
# Exceptions
# =========================================================

class AckServiceError(Exception):
    """Base ACK service exception."""


class AckValidationError(
    AckServiceError
):
    """ACK payload invalid."""


class AckAlreadyProcessedError(
    AckServiceError
):
    """ACK already processed."""


class AckTimeoutError(
    AckServiceError
):
    """ACK timeout reached."""


# =========================================================
# ACK Service
# =========================================================

class AckService:
    """
    Reliable ACK orchestration layer.

    Responsibilities
    ----------------------------------------------------
    - ACK generation
    - ACK validation
    - ACK timeout tracking
    - delivery completion
    - duplicate ACK detection
    - pending ACK monitoring
    - retransmission signaling

    Architecture
    ----------------------------------------------------
        DeliveryService
              ↓
          AckService
              ↓
         QueueStore
    """

    DEFAULT_ACK_TIMEOUT_SECONDS = 30

    MONITOR_INTERVAL_SECONDS = 5

    ACK_TYPE = "delivery_ack"

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        queue_store: Optional[
            QueueStore
        ] = None,

        delivery_service: Optional[
            DeliveryService
        ] = None,
    ) -> None:

        self.queue_store = (
            queue_store
            or QueueStore()
        )

        self.delivery_service = (
            delivery_service
        )

        self.logger = logging.getLogger(
            self.__class__.__name__
        )

        self._running = False

        self._monitor_thread: (
            threading.Thread | None
        ) = None

        self._lock = threading.RLock()

    # =====================================================
    # Lifecycle
    # =====================================================

    def start(self) -> None:

        with self._lock:

            if self._running:
                return

            self._running = True

            self._monitor_thread = (
                threading.Thread(
                    target=self._monitor_loop,
                    daemon=True,
                )
            )

            self._monitor_thread.start()

            self.logger.info(
                "AckService started."
            )

    def stop(self) -> None:

        with self._lock:

            self._running = False

            self.logger.info(
                "AckService stopped."
            )

    # =====================================================
    # ACK Creation
    # =====================================================

    def create_ack(
        self,
        *,
        message_id: str,
        receiver_id: str,
    ) -> Dict[str, str]:
        """
        Create ACK payload.
        """

        return {
            "type": self.ACK_TYPE,

            "message_id": message_id,

            "receiver_id": receiver_id,

            "acknowledged_at": (
                self._utc_now_iso()
            ),
        }

    # =====================================================
    # ACK Processing
    # =====================================================

    def process_ack(
        self,
        *,
        ack_payload: Dict[str, str],
    ) -> DeliveryRecord:
        """
        Validate + process ACK.
        """

        self._validate_ack_payload(
            ack_payload
        )

        message_id = ack_payload[
            "message_id"
        ]

        record = self.queue_store.get(
            message_id
        )

        if record.ack_received:

            raise (
                AckAlreadyProcessedError(
                    f"ACK already processed: "
                    f"{message_id}"
                )
            )

        updated = record.copy_with(
            ack_received=True,

            ack_received_at=(
                ack_payload[
                    "acknowledged_at"
                ]
            ),

            state=(
                DeliveryState
                .DELIVERED
            ),

            updated_at=(
                self._utc_now_iso()
            ),
        )

        self.queue_store.save(
            updated
        )

        self.logger.info(
            "ACK processed: %s",
            message_id,
        )

        return updated

    # =====================================================
    # ACK Validation
    # =====================================================

    def validate_ack(
        self,
        *,
        ack_payload: Dict[str, str],
    ) -> bool:
        """
        Public validation helper.
        """

        try:

            self._validate_ack_payload(
                ack_payload
            )

            return True

        except Exception:
            return False

    def _validate_ack_payload(
        self,
        payload: Dict[str, str],
    ) -> None:

        if not isinstance(
            payload,
            dict,
        ):
            raise AckValidationError(
                "ACK payload must be dict."
            )

        required = (
            "type",
            "message_id",
            "receiver_id",
            "acknowledged_at",
        )

        for field in required:

            if (
                field not in payload
            ):
                raise (
                    AckValidationError(
                        f"Missing ACK field: "
                        f"{field}"
                    )
                )

        if (
            payload["type"]
            != self.ACK_TYPE
        ):
            raise AckValidationError(
                "Invalid ACK type."
            )

    # =====================================================
    # Pending ACK Monitoring
    # =====================================================

    def check_ack_timeouts(
        self,
    ) -> list[DeliveryRecord]:
        """
        Find messages waiting too long for ACK.
        """

        pending = (
            self.queue_store
            .get_pending_messages()
        )

        now = datetime.now(
            timezone.utc
        )

        expired: list[
            DeliveryRecord
        ] = []

        for record in pending:

            if record.ack_received:
                continue

            if record.sent_at is None:
                continue

            try:

                sent_at = (
                    datetime.fromisoformat(
                        record.sent_at.replace(
                            "Z",
                            "+00:00",
                        )
                    )
                )

            except Exception:
                continue

            delta = (
                now - sent_at
            ).total_seconds()

            if (
                delta
                > self.DEFAULT_ACK_TIMEOUT_SECONDS
            ):

                expired.append(
                    record
                )

        return expired

    # =====================================================
    # Retransmission Marking
    # =====================================================

    def mark_for_retry(
        self,
        *,
        message_id: str,
    ) -> DeliveryRecord:

        record = self.queue_store.get(
            message_id
        )

        updated = record.copy_with(
            state=(
                DeliveryState
                .RETRY_PENDING
            ),

            retry_count=(
                record.retry_count
                + 1
            ),

            updated_at=(
                self._utc_now_iso()
            ),
        )

        self.queue_store.save(
            updated
        )

        self.logger.warning(
            "Marked for retry: %s",
            message_id,
        )

        return updated

    # =====================================================
    # ACK Status
    # =====================================================

    def is_acknowledged(
        self,
        *,
        message_id: str,
    ) -> bool:

        try:

            record = (
                self.queue_store.get(
                    message_id
                )
            )

            return bool(
                record.ack_received
            )

        except Exception:
            return False

    # =====================================================
    # Metrics
    # =====================================================

    def metrics(
        self,
    ) -> dict:

        pending = (
            self.queue_store
            .get_pending_messages()
        )

        delivered = 0

        for record in pending:

            if (
                record.state
                == DeliveryState.DELIVERED
            ):
                delivered += 1

        timeouts = len(
            self.check_ack_timeouts()
        )

        return {
            "pending_ack":
                len(pending),

            "ack_timeouts":
                timeouts,

            "delivered":
                delivered,

            "running":
                self._running,
        }

    # =====================================================
    # Monitor Loop
    # =====================================================

    def _monitor_loop(
        self,
    ) -> None:

        while self._running:

            try:

                expired = (
                    self
                    .check_ack_timeouts()
                )

                for record in expired:

                    self.logger.warning(
                        "ACK timeout detected: %s",
                        record.message_id,
                    )

                    self.mark_for_retry(
                        message_id=(
                            record.message_id
                        )
                    )

            except Exception as exc:

                self.logger.exception(
                    "ACK monitor failure: %s",
                    exc,
                )

            time.sleep(
                self.MONITOR_INTERVAL_SECONDS
            )

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
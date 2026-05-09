from __future__ import annotations

import json
import logging
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
)

from storage.message_store import (
    MessageStore,
)

from services.protocol_service import (
    ProtocolService,
    ProtocolServiceError,
)

from services.queue_service import (
    QueueService,
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

class DeliveryServiceError(Exception):
    """Base delivery service exception."""


class TransportUnavailableError(
    DeliveryServiceError
):
    """Transport layer unavailable."""


class DeliveryAckTimeoutError(
    DeliveryServiceError
):
    """ACK timeout."""


# =========================================================
# Delivery Service
# =========================================================

class DeliveryService:
    """
    High-level reliable message delivery layer.

    Responsibilities:
    -----------------------------------------------------
    - outbound delivery orchestration
    - ACK lifecycle
    - delivery guarantees
    - retry coordination
    - dead-letter routing
    - offline-safe queueing
    - transport abstraction
    - delivery metrics
    - message persistence

    Architecture:
    -----------------------------------------------------
        UI
         ↓
    DeliveryService
         ↓
    QueueService
         ↓
    ProtocolService
         ↓
    Transport Layer
    """

    DEFAULT_ACK_TIMEOUT_SECONDS = 30

    HEALTHCHECK_INTERVAL_SECONDS = 5

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        queue_service: Optional[
            QueueService
        ] = None,

        queue_store: Optional[
            QueueStore
        ] = None,

        message_store: Optional[
            MessageStore
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

        transport_send_callback: Optional[
            Callable[[dict], None]
        ] = None,
    ) -> None:

        self.queue_store = (
            queue_store
            or QueueStore()
        )

        self.message_store = (
            message_store
            or MessageStore()
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

        self.queue_service = (
            queue_service
            or QueueService(
                queue_store=self.queue_store,
                protocol_service=(
                    self.protocol_service
                ),
                session_service=(
                    self.session_service
                ),
                ratchet_service=(
                    self.ratchet_service
                ),
            )
        )

        self.transport_send_callback = (
            transport_send_callback
        )

        self._running = False

        self._health_thread: (
            threading.Thread | None
        ) = None

        self._lock = threading.RLock()

        self.logger = logging.getLogger(
            self.__class__.__name__
        )

    # =====================================================
    # Lifecycle
    # =====================================================

    def start(self) -> None:

        with self._lock:

            if self._running:
                return

            self._running = True

            self.queue_service.start()

            self._health_thread = (
                threading.Thread(
                    target=self._health_loop,
                    daemon=True,
                )
            )

            self._health_thread.start()

            self.logger.info(
                "DeliveryService started."
            )

    def stop(self) -> None:

        with self._lock:

            self._running = False

            self.queue_service.stop()

            self.logger.info(
                "DeliveryService stopped."
            )

    # =====================================================
    # Send Message
    # =====================================================

    def send_message(
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
        Main outbound messaging entrypoint.
        """

        record = (
            self.queue_service.enqueue_message(
                sender_profile=sender_profile,

                receiver_contact=(
                    receiver_contact
                ),

                plaintext=plaintext,

                priority=priority,

                metadata=metadata,
            )
        )

        self.logger.info(
            "Message queued: %s",
            record.message_id,
        )

        return record

    # =====================================================
    # Receive Envelope
    # =====================================================

    def receive_envelope(
        self,
        *,
        receiver_profile: dict,
        sender_contact: dict,
        envelope: dict,
    ) -> dict:
        """
        Receive + decrypt + persist message.
        """

        result = (
            self.protocol_service
            .receive_message(
                receiver_profile=(
                    receiver_profile
                ),

                sender_contact=(
                    sender_contact
                ),

                envelope=envelope,

                verify_signature=True,

                enforce_replay_protection=True,
            )
        )

        plaintext = (
            result.get("plaintext")
            or ""
        )

        self.message_store.save_received_message(
            sender_id=str(
                sender_contact.get(
                    "name"
                )
            ),

            receiver_id=str(
                receiver_profile.get(
                    "name"
                )
            ),

            plaintext=plaintext,

            encrypted_envelope=envelope,
        )

        return result

    # =====================================================
    # ACK
    # =====================================================

    def acknowledge_message(
        self,
        *,
        message_id: str,
        ack_message_id: str,
    ) -> None:

        self.queue_service.acknowledge_delivery(
            message_id=message_id,

            ack_message_id=(
                ack_message_id
            ),
        )

        self.logger.info(
            "ACK received for %s",
            message_id,
        )

    # =====================================================
    # Transport
    # =====================================================

    def deliver_envelope(
        self,
        *,
        envelope: dict,
    ) -> None:
        """
        Actual transport delivery hook.

        Replace later with:
        - websocket
        - tcp
        - p2p
        - tor
        """

        if (
            self.transport_send_callback
            is None
        ):
            raise (
                TransportUnavailableError(
                    "No transport callback configured."
                )
            )

        self.transport_send_callback(
            envelope
        )

    # =====================================================
    # Retry Monitoring
    # =====================================================

    def monitor_pending_acks(
        self,
    ) -> int:
        """
        Detect ACK timeouts.
        """

        pending = (
            self.queue_store
            .get_pending_messages()
        )

        now = datetime.now(
            timezone.utc
        )

        expired = 0

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

                expired += 1

                self.logger.warning(
                    "ACK timeout: %s",
                    record.message_id,
                )

        return expired

    # =====================================================
    # Metrics
    # =====================================================

    def metrics(self) -> dict:

        pending = (
            self.queue_store
            .get_pending_messages()
        )

        dead = (
            self.queue_store
            .get_dead_letters()
        )

        return {
            "pending_messages":
                len(pending),

            "dead_letters":
                len(dead),

            "queue_total":
                self.queue_store.count(),

            "running":
                self._running,
        }

    # =====================================================
    # Background Health Loop
    # =====================================================

    def _health_loop(
        self,
    ) -> None:

        while self._running:

            try:

                self.monitor_pending_acks()

            except Exception as exc:

                self.logger.exception(
                    "Health loop failure: %s",
                    exc,
                )

            time.sleep(
                self.HEALTHCHECK_INTERVAL_SECONDS
            )

    # =====================================================
    # Dead Letter
    # =====================================================

    def get_dead_letters(
        self,
    ) -> list[DeliveryRecord]:

        return (
            self.queue_store
            .get_dead_letters()
        )

    # =====================================================
    # Retry Manual
    # =====================================================

    def retry_dead_letter(
        self,
        *,
        message_id: str,
    ) -> None:

        record = self.queue_store.get(
            message_id
        )

        updated = record.copy_with(
            state=(
                DeliveryState
                .RETRY_PENDING
            ),

            retry_count=0,

            next_retry_at=(
                self._utc_now_iso()
            ),

            updated_at=(
                self._utc_now_iso()
            ),
        )

        self.queue_store.save(
            updated
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
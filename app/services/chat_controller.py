from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from ..transport.transport_packet import (
    TransportPacket,
)

from ..transport.transport_events import (
    TransportEvent,
    TransportEventType,
)

from .event_bus import (
    EventBus,
)

from .inbound_pipeline import (
    InboundPipeline,
)

from .outbound_pipeline import (
    OutboundPipeline,
)

from ..storage.message_store import (
    MessageStore,
)

from .session_service import (
    SessionService,
)

from .queue_service import (
    QueueService,
)

from .delivery_service import (
    DeliveryService,
)

from .ack_service import (
    AckService,
)

from .protocol_service import (
    ProtocolService,
)

from .ratchet_service import (
    RatchetService,
)


# =========================================================
# Exceptions
# =========================================================

class ChatControllerError(Exception):
    """Base controller exception."""


class PeerNotFoundError(
    ChatControllerError
):
    """Peer/contact not found."""


class ProfileNotLoadedError(
    ChatControllerError
):
    """No active profile loaded."""


# =========================================================
# Chat Controller
# =========================================================

class ChatController:
    """
    High-level application layer.

    Responsibilities
    ------------------------------------------------
    - app orchestration
    - UI integration
    - peer management
    - send/receive abstraction
    - event subscriptions
    - runtime lifecycle

    UI should interact ONLY with this layer.
    """

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        protocol_service: ProtocolService,
        session_service: SessionService,
        ratchet_service: RatchetService,
        queue_service: QueueService,
        delivery_service: DeliveryService,
        ack_service: AckService,
        message_store: MessageStore,
        transport,
    ) -> None:

        self._logger = logging.getLogger(
            self.__class__.__name__
        )

        self.protocol_service = (
            protocol_service
        )

        self.session_service = (
            session_service
        )

        self.ratchet_service = (
            ratchet_service
        )

        self.queue_service = (
            queue_service
        )

        self.delivery_service = (
            delivery_service
        )

        self.ack_service = (
            ack_service
        )

        self.message_store = (
            message_store
        )

        self.transport = transport

        # =============================================
        # Event bus
        # =============================================

        self.event_bus = EventBus()

        # =============================================
        # Runtime state
        # =============================================

        self.profile: Optional[
            dict
        ] = None

        self.contacts: Dict[
            str,
            dict,
        ] = {}

        # =============================================
        # Pipelines
        # =============================================

        self.inbound_pipeline = (
            InboundPipeline(
                protocol_service=(
                    protocol_service
                ),

                session_service=(
                    session_service
                ),

                delivery_service=(
                    delivery_service
                ),

                ack_service=(
                    ack_service
                ),

                message_store=(
                    message_store
                ),

                emit_event=(
                    self.event_bus.emit
                ),
            )
        )

        self.outbound_pipeline = (
            OutboundPipeline(
                protocol_service=(
                    protocol_service
                ),

                session_service=(
                    session_service
                ),

                ratchet_service=(
                    ratchet_service
                ),

                delivery_service=(
                    delivery_service
                ),

                queue_service=(
                    queue_service
                ),

                message_store=(
                    message_store
                ),

                transport=transport,

                emit_event=(
                    self.event_bus.emit
                ),
            )
        )

    # =====================================================
    # Lifecycle
    # =====================================================

    async def start(
        self,
    ) -> None:

        await self.event_bus.start()

        self.transport.on_packet(
            self._on_transport_packet
        )

        self._logger.info(
            "Chat controller started."
        )

    async def stop(
        self,
    ) -> None:

        await self.event_bus.stop()

        self._logger.info(
            "Chat controller stopped."
        )

    # =====================================================
    # Profile Management
    # =====================================================

    def load_profile(
        self,
        profile: dict,
    ) -> None:

        self.profile = profile

    def current_profile(
        self,
    ) -> dict:

        if not self.profile:

            raise (
                ProfileNotLoadedError(
                    "No active profile."
                )
            )

        return self.profile

    # =====================================================
    # Contacts
    # =====================================================

    def add_contact(
        self,
        contact: dict,
    ) -> None:

        peer_id = str(
            contact["id"]
        )

        self.contacts[
            peer_id
        ] = contact

    def remove_contact(
        self,
        peer_id: str,
    ) -> None:

        self.contacts.pop(
            peer_id,
            None,
        )

    def get_contact(
        self,
        peer_id: str,
    ) -> dict:

        contact = (
            self.contacts.get(
                peer_id
            )
        )

        if not contact:

            raise (
                PeerNotFoundError(
                    peer_id
                )
            )

        return contact

    def list_contacts(
        self,
    ) -> List[dict]:

        return list(
            self.contacts.values()
        )

    # =====================================================
    # Send Message
    # =====================================================

    async def send_message(
        self,
        *,
        peer_id: str,
        plaintext: str,
        metadata: Optional[
            dict
        ] = None,
    ) -> dict:

        profile = (
            self.current_profile()
        )

        contact = (
            self.get_contact(
                peer_id
            )
        )

        ctx = (
            await self.outbound_pipeline.execute(
                sender_profile=profile,

                receiver_contact=contact,

                plaintext=plaintext,

                metadata=(
                    metadata or {}
                ),
            )
        )

        return {
            "packet_id":
                ctx.packet.packet_id
                if ctx.packet
                else None,

            "success":
                not ctx.rejected,
        }

    # =====================================================
    # Receive Message
    # =====================================================

    async def receive_packet(
        self,
        packet: TransportPacket,
    ) -> dict:

        profile = (
            self.current_profile()
        )

        ctx = (
            await self.inbound_pipeline.execute(
                packet=packet,

                receiver_profile=(
                    profile
                ),
            )
        )

        return {
            "verified":
                ctx.verified,

            "plaintext":
                ctx.plaintext,

            "rejected":
                ctx.rejected,
        }

    # =====================================================
    # Transport Hook
    # =====================================================

    async def _on_transport_packet(
        self,
        packet: TransportPacket,
    ) -> None:

        try:

            await self.receive_packet(
                packet
            )

        except Exception as exc:

            self._logger.exception(
                "Inbound packet failed: %s",
                exc,
            )

            await self.event_bus.emit(
                TransportEvent(
                    event_type=(
                        TransportEventType.ERROR
                    ),

                    peer_id=(
                        packet.sender_peer_id
                    ),

                    packet_id=(
                        packet.packet_id
                    ),

                    metadata={
                        "error":
                            str(exc)
                    },
                )
            )

    # =====================================================
    # Event Subscriptions
    # =====================================================

    def on(
        self,
        event_type,
        callback,
    ) -> None:

        self.event_bus.subscribe(
            event_type,
            callback,
        )

    def off(
        self,
        event_type,
        callback,
    ) -> None:

        self.event_bus.unsubscribe(
            event_type,
            callback,
        )

    # =====================================================
    # Message APIs
    # =====================================================

    def get_conversation(
        self,
        peer_id: str,
        *,
        limit: int = 100,
    ) -> List[dict]:

        return (
            self.message_store.get_conversation(
                peer_id=peer_id,
                limit=limit,
            )
        )

    def get_message(
        self,
        packet_id: str,
    ) -> Optional[dict]:

        return (
            self.message_store.get_message(
                packet_id
            )
        )

    # =====================================================
    # Sessions
    # =====================================================

    def get_session(
        self,
        peer_id: str,
    ):

        return (
            self.session_service.find_session_by_peer(
                peer_id
            )
        )

    def reset_session(
        self,
        peer_id: str,
    ) -> None:

        self.session_service.delete_session(
            peer_id
        )

    # =====================================================
    # Queue APIs
    # =====================================================

    def pending_packets(
        self,
    ) -> List[TransportPacket]:

        return (
            self.queue_service.pending_packets()
        )

    # =====================================================
    # Delivery APIs
    # =====================================================

    def delivery_status(
        self,
        packet_id: str,
    ):

        return (
            self.delivery_service.delivery_status(
                packet_id
            )
        )

    # =====================================================
    # Metrics
    # =====================================================

    def metrics(
        self,
    ) -> Dict[str, Any]:

        return {

            "contacts":
                len(self.contacts),

            "event_bus":
                self.event_bus.metrics(),

            "queue_size":
                self.queue_service.size(),

            "sessions":
                self.session_service.count_sessions(),
        }

    # =====================================================
    # Utility
    # =====================================================

    async def wait_until_idle(
        self,
    ) -> None:

        await self.event_bus.wait_until_idle()

    # =====================================================
    # Context Manager
    # =====================================================

    async def __aenter__(
        self,
    ) -> "ChatController":

        await self.start()

        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        tb,
    ) -> None:

        await self.stop()


__all__ = [

    "ChatController",

    "ChatControllerError",

    "PeerNotFoundError",

    "ProfileNotLoadedError",
]
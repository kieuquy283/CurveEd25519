from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Dict, Optional

from ..core.packet_types import (
    PacketType,
    normalize_packet_type,
    packet_requires_ack,
)

from ..transport.transport_packet import (
    TransportPacket,
)

from ..transport.transport_events import (
    TransportEvent,
    TransportEventType,
)

from .ack_service import AckService

from .delivery_service import (
    DeliveryService,
)

from .protocol_service import (
    ProtocolService,
    ProtocolReplayError,
    ProtocolSignatureError,
    ProtocolDecryptError,
)

from .queue_service import QueueService

from .ratchet_service import (
    RatchetService,
)

from .session_service import (
    SessionService,
)


# =========================================================
# Exceptions
# =========================================================

class MessageRouterError(Exception):
    """Base router exception."""


class UnsupportedPacketError(
    MessageRouterError
):
    """Unsupported packet type."""


class TransportUnavailableError(
    MessageRouterError
):
    """No transport registered."""


# =========================================================
# Message Router
# =========================================================

class MessageRouter:
    """
    Central runtime orchestration layer.

    Responsibilities
    ------------------------------------------------

    OUTBOUND:
        user message
            -> session
            -> ratchet
            -> protocol encrypt
            -> queue
            -> transport send

    INBOUND:
        transport packet
            -> dispatch
            -> replay validation
            -> decrypt
            -> store
            -> ACK
            -> emit events
    """

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        protocol_service: Optional[
            ProtocolService
        ] = None,

        session_service: Optional[
            SessionService
        ] = None,

        ratchet_service: Optional[
            RatchetService
        ] = None,

        delivery_service: Optional[
            DeliveryService
        ] = None,

        ack_service: Optional[
            AckService
        ] = None,

        queue_service: Optional[
            QueueService
        ] = None,
    ) -> None:

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

        self.delivery_service = (
            delivery_service
            or DeliveryService()
        )

        self.ack_service = (
            ack_service
            or AckService()
        )

        self.queue_service = (
            queue_service
            or QueueService()
        )

        self._transport = None

        self._logger = logging.getLogger(
            self.__class__.__name__
        )

        # =================================================
        # Event callbacks
        # =================================================

        self._event_handlers: list[
            Callable[
                [TransportEvent],
                Awaitable[None],
            ]
        ] = []

    # =====================================================
    # Transport
    # =====================================================

    def register_transport(
        self,
        transport,
    ) -> None:

        self._transport = transport

    def has_transport(self) -> bool:

        return self._transport is not None

    # =====================================================
    # Event System
    # =====================================================

    def register_event_handler(
        self,
        callback: Callable[
            [TransportEvent],
            Awaitable[None],
        ],
    ) -> None:

        self._event_handlers.append(
            callback
        )

    async def emit_event(
        self,
        event: TransportEvent,
    ) -> None:

        for handler in (
            self._event_handlers
        ):

            try:
                await handler(event)

            except Exception as exc:
                self._logger.exception(
                    "Event handler failed: %s",
                    exc,
                )

    # =====================================================
    # OUTBOUND
    # =====================================================

    async def send_message(
        self,
        *,
        sender_profile: dict,
        receiver_contact: dict,
        plaintext: str,
        metadata: Optional[
            dict
        ] = None,
    ) -> TransportPacket:
        """
        High-level secure message send.
        """

        if not self._transport:
            raise (
                TransportUnavailableError(
                    "No transport registered."
                )
            )

        # =================================================
        # Session lookup
        # =================================================

        session = (
            self.session_service.get_or_create_session(
                local_profile=sender_profile,
                remote_contact=receiver_contact,
            )
        )

        # =================================================
        # Ratchet outbound
        # =================================================

        self.ratchet_service.advance_send_ratchet(
            session
        )

        # =================================================
        # Protocol encrypt
        # =================================================

        protocol_result = (
            self.protocol_service.send_message(
                sender_profile=sender_profile,
                receiver_contact=receiver_contact,
                plaintext=plaintext,
            )
        )

        envelope = (
            protocol_result["envelope"]
        )

        # =================================================
        # Build transport packet
        # =================================================

        packet = TransportPacket.message_packet(
            sender_peer_id=(
                sender_profile["id"]
            ),

            receiver_peer_id=(
                receiver_contact["id"]
            ),

            payload=envelope,

            metadata=metadata or {},
        )

        # =================================================
        # Queue packet
        # =================================================

        self.queue_service.enqueue_packet(
            packet
        )

        # =================================================
        # Delivery tracking
        # =================================================

        self.delivery_service.track_outbound_packet(
            packet
        )

        # =================================================
        # Send transport
        # =================================================

        await self._transport.send_packet(
            packet
        )

        # =================================================
        # Event
        # =================================================

        await self.emit_event(
            TransportEvent(
                event_type=(
                    TransportEventType.PACKET_SENT
                ),

                packet_id=packet.packet_id,

                peer_id=(
                    packet.receiver_peer_id
                ),

                metadata={
                    "packet_type": (
                        packet.packet_type.value
                    ),
                },
            )
        )

        return packet

    # =====================================================
    # INBOUND DISPATCH
    # =====================================================

    async def handle_packet(
        self,
        packet: TransportPacket,
        *,
        receiver_profile: Optional[
            dict
        ] = None,
    ) -> None:
        """
        Central inbound dispatcher.
        """

        packet_type = normalize_packet_type(
            packet.packet_type
        )

        # =================================================
        # Dispatch map
        # =================================================

        handlers = {

            PacketType.MESSAGE:
                self._handle_message_packet,

            PacketType.ACK:
                self._handle_ack_packet,

            PacketType.PING:
                self._handle_ping_packet,

            PacketType.PONG:
                self._handle_pong_packet,

            PacketType.REKEY:
                self._handle_rekey_packet,

            PacketType.SESSION_INIT:
                self._handle_session_init_packet,

            PacketType.SESSION_CLOSE:
                self._handle_session_close_packet,
        }

        handler = handlers.get(
            packet_type
        )

        if handler is None:
            raise UnsupportedPacketError(
                f"Unsupported packet type: "
                f"{packet_type}"
            )

        await handler(
            packet,
            receiver_profile=receiver_profile,
        )

    # =====================================================
    # MESSAGE
    # =====================================================

    async def _handle_message_packet(
        self,
        packet: TransportPacket,
        *,
        receiver_profile: Optional[
            dict,
        ] = None,
    ) -> None:

        try:

            result = (
                self.protocol_service.receive_message(
                    receiver_profile=(
                        receiver_profile
                    ),
                    envelope=packet.payload,
                )
            )

            plaintext = (
                result.get("plaintext")
            )

            # =============================================
            # Delivery tracking
            # =============================================

            self.delivery_service.mark_delivered(
                packet.packet_id
            )

            # =============================================
            # Ratchet inbound
            # =============================================

            session = (
                self.session_service.find_session_by_peer(
                    packet.sender_peer_id
                )
            )

            if session:
                self.ratchet_service.advance_receive_ratchet(
                    session
                )

            # =============================================
            # ACK
            # =============================================

            if packet_requires_ack(
                packet.packet_type
            ):
                await self.send_ack(
                    packet
                )

            # =============================================
            # Event
            # =============================================

            await self.emit_event(
                TransportEvent(
                    event_type=(
                        TransportEventType.PACKET_RECEIVED
                    ),

                    packet_id=(
                        packet.packet_id
                    ),

                    peer_id=(
                        packet.sender_peer_id
                    ),

                    message_id=(
                        packet.payload["header"][
                            "message_id"
                        ]
                    ),

                    metadata={
                        "plaintext":
                            plaintext,
                    },
                )
            )

        except (
            ProtocolReplayError,
            ProtocolSignatureError,
            ProtocolDecryptError,
        ) as exc:

            self._logger.warning(
                "Inbound packet rejected: %s",
                exc,
            )

            await self.emit_event(
                TransportEvent.from_exception(
                    event_type=(
                        TransportEventType.ERROR
                    ),
                    exc=exc,
                    peer_id=(
                        packet.sender_peer_id
                    ),
                )
            )

    # =====================================================
    # ACK
    # =====================================================

    async def send_ack(
        self,
        packet: TransportPacket,
    ) -> None:

        if not self._transport:
            return

        ack_packet = (
            TransportPacket.ack_packet(
                sender_peer_id=(
                    packet.receiver_peer_id
                ),

                receiver_peer_id=(
                    packet.sender_peer_id
                ),

                ack_packet_id=(
                    packet.packet_id
                ),
            )
        )

        await self._transport.send_packet(
            ack_packet
        )

    async def _handle_ack_packet(
        self,
        packet: TransportPacket,
        *,
        receiver_profile: Optional[
            dict,
        ] = None,
    ) -> None:

        acked_packet_id = (
            packet.payload.get(
                "ack_packet_id"
            )
        )

        if not acked_packet_id:
            return

        self.ack_service.mark_acked(
            acked_packet_id
        )

        self.delivery_service.mark_acked(
            acked_packet_id
        )

        await self.emit_event(
            TransportEvent(
                event_type=(
                    TransportEventType.PACKET_ACKED
                ),

                packet_id=(
                    acked_packet_id
                ),

                peer_id=(
                    packet.sender_peer_id
                ),
            )
        )

    # =====================================================
    # PING / PONG
    # =====================================================

    async def _handle_ping_packet(
        self,
        packet: TransportPacket,
        *,
        receiver_profile: Optional[
            dict,
        ] = None,
    ) -> None:

        if not self._transport:
            return

        pong_packet = (
            TransportPacket.pong_packet(
                sender_peer_id=(
                    packet.receiver_peer_id
                ),

                receiver_peer_id=(
                    packet.sender_peer_id
                ),
            )
        )

        await self._transport.send_packet(
            pong_packet
        )

    async def _handle_pong_packet(
        self,
        packet: TransportPacket,
        *,
        receiver_profile: Optional[
            dict,
        ] = None,
    ) -> None:

        await self.emit_event(
            TransportEvent(
                event_type=(
                    TransportEventType.HEARTBEAT
                ),

                peer_id=(
                    packet.sender_peer_id
                ),
            )
        )

    # =====================================================
    # REKEY
    # =====================================================

    async def _handle_rekey_packet(
        self,
        packet: TransportPacket,
        *,
        receiver_profile: Optional[
            dict,
        ] = None,
    ) -> None:

        session = (
            self.session_service.find_session_by_peer(
                packet.sender_peer_id
            )
        )

        if not session:
            return

        self.ratchet_service.perform_rekey(
            session
        )

        await self.emit_event(
            TransportEvent(
                event_type=(
                    TransportEventType.SESSION_REKEYED
                ),

                peer_id=(
                    packet.sender_peer_id
                ),
            )
        )

    # =====================================================
    # SESSION
    # =====================================================

    async def _handle_session_init_packet(
        self,
        packet: TransportPacket,
        *,
        receiver_profile: Optional[
            dict,
        ] = None,
    ) -> None:

        self.session_service.accept_session(
            packet.payload
        )

        await self.emit_event(
            TransportEvent(
                event_type=(
                    TransportEventType.SESSION_CREATED
                ),

                peer_id=(
                    packet.sender_peer_id
                ),
            )
        )

    async def _handle_session_close_packet(
        self,
        packet: TransportPacket,
        *,
        receiver_profile: Optional[
            dict,
        ] = None,
    ) -> None:

        self.session_service.close_session(
            packet.sender_peer_id
        )

        await self.emit_event(
            TransportEvent(
                event_type=(
                    TransportEventType.SESSION_EXPIRED
                ),

                peer_id=(
                    packet.sender_peer_id
                ),
            )
        )

    # =====================================================
    # Background Runtime
    # =====================================================

    async def start_background_tasks(
        self,
    ) -> None:

        asyncio.create_task(
            self._queue_worker()
        )

    async def _queue_worker(
        self,
    ) -> None:

        while True:

            try:

                queued_packet = (
                    self.queue_service.dequeue_packet()
                )

                if (
                    queued_packet
                    and self._transport
                ):
                    await self._transport.send_packet(
                        queued_packet
                    )

            except Exception as exc:

                self._logger.exception(
                    "Queue worker failed: %s",
                    exc,
                )

            await asyncio.sleep(0.05)


__all__ = [
    "MessageRouter",
    "MessageRouterError",
    "UnsupportedPacketError",
    "TransportUnavailableError",
]
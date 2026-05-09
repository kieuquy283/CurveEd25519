from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
)

from ..core.packet_types import (
    PacketType,
)

from ..transport.transport_packet import (
    TransportPacket,
)

from ..transport.transport_events import (
    TransportEvent,
    TransportEventType,
)

from .delivery_service import (
    DeliveryService,
)

from .protocol_service import (
    ProtocolService,
)

from .queue_service import (
    QueueService,
)

from .ratchet_service import (
    RatchetService,
)

from .session_service import (
    SessionService,
)

from ..storage.message_store import (
    MessageStore,
)


# =========================================================
# Exceptions
# =========================================================

class OutboundPipelineError(Exception):
    """Base outbound pipeline exception."""


class OutboundMiddlewareError(
    OutboundPipelineError
):
    """Outbound middleware failure."""


# =========================================================
# Context
# =========================================================

@dataclass(slots=True)
class OutboundContext:
    """
    Shared outbound runtime state.
    """

    sender_profile: dict

    receiver_contact: dict

    plaintext: str

    metadata: Dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    session: Optional[Any] = None

    envelope: Optional[dict] = None

    packet: Optional[
        TransportPacket
    ] = None

    protocol_result: Optional[
        dict
    ] = None

    rejected: bool = False


# =========================================================
# Middleware Base
# =========================================================

class OutboundMiddleware:

    async def process(
        self,
        ctx: OutboundContext,
        next_call: Callable[
            [],
            Awaitable[None],
        ],
    ) -> None:
        raise NotImplementedError


# =========================================================
# Session Middleware
# =========================================================

class SessionMiddleware(
    OutboundMiddleware
):

    def __init__(
        self,
        session_service: SessionService,
    ) -> None:

        self.session_service = (
            session_service
        )

    async def process(
        self,
        ctx: OutboundContext,
        next_call,
    ) -> None:

        session = (
            self.session_service.get_or_create_session(
                local_profile=(
                    ctx.sender_profile
                ),

                remote_contact=(
                    ctx.receiver_contact
                ),
            )
        )

        ctx.session = session

        await next_call()


# =========================================================
# Ratchet Middleware
# =========================================================

class RatchetMiddleware(
    OutboundMiddleware
):

    def __init__(
        self,
        ratchet_service: RatchetService,
    ) -> None:

        self.ratchet_service = (
            ratchet_service
        )

    async def process(
        self,
        ctx: OutboundContext,
        next_call,
    ) -> None:

        if ctx.session:

            self.ratchet_service.advance_send_ratchet(
                ctx.session
            )

        await next_call()


# =========================================================
# Encrypt Middleware
# =========================================================

class EncryptMiddleware(
    OutboundMiddleware
):

    def __init__(
        self,
        protocol_service: ProtocolService,
    ) -> None:

        self.protocol_service = (
            protocol_service
        )

    async def process(
        self,
        ctx: OutboundContext,
        next_call,
    ) -> None:

        try:

            result = (
                self.protocol_service.send_message(
                    sender_profile=(
                        ctx.sender_profile
                    ),

                    receiver_contact=(
                        ctx.receiver_contact
                    ),

                    plaintext=(
                        ctx.plaintext
                    ),
                )
            )

            ctx.protocol_result = result

            ctx.envelope = result[
                "envelope"
            ]

        except Exception as exc:

            ctx.rejected = True

            raise OutboundMiddlewareError(
                f"Encryption failed: {exc}"
            ) from exc

        await next_call()


# =========================================================
# Packet Build Middleware
# =========================================================

class PacketBuildMiddleware(
    OutboundMiddleware
):

    async def process(
        self,
        ctx: OutboundContext,
        next_call,
    ) -> None:

        if not ctx.envelope:

            raise (
                OutboundMiddlewareError(
                    "Missing envelope."
                )
            )

        ctx.packet = (
            TransportPacket.message_packet(
                sender_peer_id=(
                    ctx.sender_profile["id"]
                ),

                receiver_peer_id=(
                    ctx.receiver_contact["id"]
                ),

                payload=ctx.envelope,

                metadata=ctx.metadata,
            )
        )

        await next_call()


# =========================================================
# Store Middleware
# =========================================================

class StoreMiddleware(
    OutboundMiddleware
):

    def __init__(
        self,
        message_store: MessageStore,
    ) -> None:

        self.message_store = (
            message_store
        )

    async def process(
        self,
        ctx: OutboundContext,
        next_call,
    ) -> None:

        if ctx.packet:

            self.message_store.store_outbound_message(
                sender_peer_id=(
                    ctx.sender_profile["id"]
                ),

                receiver_peer_id=(
                    ctx.receiver_contact["id"]
                ),

                packet_id=(
                    ctx.packet.packet_id
                ),

                plaintext=(
                    ctx.plaintext
                ),

                metadata=ctx.metadata,
            )

        await next_call()


# =========================================================
# Queue Middleware
# =========================================================

class QueueMiddleware(
    OutboundMiddleware
):

    def __init__(
        self,
        queue_service: QueueService,
    ) -> None:

        self.queue_service = (
            queue_service
        )

    async def process(
        self,
        ctx: OutboundContext,
        next_call,
    ) -> None:

        if ctx.packet:

            self.queue_service.enqueue_packet(
                ctx.packet
            )

        await next_call()


# =========================================================
# Delivery Middleware
# =========================================================

class DeliveryMiddleware(
    OutboundMiddleware
):

    def __init__(
        self,
        delivery_service: DeliveryService,
    ) -> None:

        self.delivery_service = (
            delivery_service
        )

    async def process(
        self,
        ctx: OutboundContext,
        next_call,
    ) -> None:

        if ctx.packet:

            self.delivery_service.track_outbound_packet(
                ctx.packet
            )

        await next_call()


# =========================================================
# Transport Middleware
# =========================================================

class TransportMiddleware(
    OutboundMiddleware
):

    def __init__(
        self,
        transport,
    ) -> None:

        self.transport = transport

    async def process(
        self,
        ctx: OutboundContext,
        next_call,
    ) -> None:

        if not ctx.packet:

            raise (
                OutboundMiddlewareError(
                    "Missing transport packet."
                )
            )

        await self.transport.send_packet(
            ctx.packet
        )

        await next_call()


# =========================================================
# Event Middleware
# =========================================================

class EventMiddleware(
    OutboundMiddleware
):

    def __init__(
        self,
        emit_callback: Callable[
            [TransportEvent],
            Awaitable[None],
        ],
    ) -> None:

        self.emit_callback = (
            emit_callback
        )

    async def process(
        self,
        ctx: OutboundContext,
        next_call,
    ) -> None:

        await next_call()

        if not ctx.packet:
            return

        event = TransportEvent(
            event_type=(
                TransportEventType.PACKET_SENT
            ),

            packet_id=(
                ctx.packet.packet_id
            ),

            peer_id=(
                ctx.receiver_contact["id"]
            ),

            metadata={

                "packet_type":
                    PacketType.MESSAGE.value,

                "plaintext":
                    ctx.plaintext,
            },
        )

        await self.emit_callback(
            event
        )


# =========================================================
# Outbound Pipeline
# =========================================================

class OutboundPipeline:
    """
    Middleware-based outbound pipeline.
    """

    def __init__(
        self,
        *,
        protocol_service: ProtocolService,

        session_service: SessionService,

        ratchet_service: RatchetService,

        delivery_service: DeliveryService,

        queue_service: QueueService,

        message_store: MessageStore,

        transport,

        emit_event: Callable[
            [TransportEvent],
            Awaitable[None],
        ],
    ) -> None:

        self._logger = logging.getLogger(
            self.__class__.__name__
        )

        self.middlewares: List[
            OutboundMiddleware
        ] = [

            SessionMiddleware(
                session_service
            ),

            RatchetMiddleware(
                ratchet_service
            ),

            EncryptMiddleware(
                protocol_service
            ),

            PacketBuildMiddleware(),

            StoreMiddleware(
                message_store
            ),

            QueueMiddleware(
                queue_service
            ),

            DeliveryMiddleware(
                delivery_service
            ),

            TransportMiddleware(
                transport
            ),

            EventMiddleware(
                emit_event
            ),
        ]

    # =====================================================
    # Execute
    # =====================================================

    async def execute(
        self,
        *,
        sender_profile: dict,

        receiver_contact: dict,

        plaintext: str,

        metadata: Optional[
            dict
        ] = None,
    ) -> OutboundContext:

        ctx = OutboundContext(
            sender_profile=(
                sender_profile
            ),

            receiver_contact=(
                receiver_contact
            ),

            plaintext=plaintext,

            metadata=metadata or {},
        )

        await self._execute_chain(
            ctx,
            0,
        )

        return ctx

    # =====================================================
    # Middleware Chain
    # =====================================================

    async def _execute_chain(
        self,
        ctx: OutboundContext,
        index: int,
    ) -> None:

        if index >= len(
            self.middlewares
        ):
            return

        middleware = (
            self.middlewares[index]
        )

        async def next_call():

            await self._execute_chain(
                ctx,
                index + 1,
            )

        try:

            await middleware.process(
                ctx,
                next_call,
            )

        except Exception as exc:

            self._logger.exception(
                "Outbound middleware failed: %s",
                exc,
            )

            raise


__all__ = [

    "OutboundPipeline",
    "OutboundContext",

    "OutboundMiddleware",

    "SessionMiddleware",
    "RatchetMiddleware",
    "EncryptMiddleware",
    "PacketBuildMiddleware",
    "StoreMiddleware",
    "QueueMiddleware",
    "DeliveryMiddleware",
    "TransportMiddleware",
    "EventMiddleware",

    "OutboundPipelineError",
    "OutboundMiddlewareError",
]
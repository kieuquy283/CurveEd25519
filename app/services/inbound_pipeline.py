from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..core.packet_types import (
    PacketType,
    packet_requires_ack,
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

from ..storage.message_store import (
    MessageStore,
)

from .protocol_service import (
    ProtocolDecryptError,
    ProtocolReplayError,
    ProtocolService,
    ProtocolSignatureError,
)

from .session_service import (
    SessionService,
)

from .ack_service import (
    AckService,
)


# =========================================================
# Exceptions
# =========================================================

class InboundPipelineError(Exception):
    """Base inbound pipeline exception."""


class MiddlewareExecutionError(
    InboundPipelineError
):
    """Middleware failed."""


# =========================================================
# Context
# =========================================================

@dataclass(slots=True)
class InboundContext:
    """
    Shared inbound runtime state.
    """

    packet: TransportPacket

    receiver_profile: Optional[
        dict
    ] = None

    session: Optional[Any] = None

    plaintext: Optional[str] = None

    protocol_result: Optional[
        dict
    ] = None

    verified: bool = False

    rejected: bool = False

    metadata: Dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )


# =========================================================
# Middleware Base
# =========================================================

class InboundMiddleware:
    """
    Abstract middleware.
    """

    async def process(
        self,
        ctx: InboundContext,
        next_call: Callable[
            [],
            Awaitable[None],
        ],
    ) -> None:
        raise NotImplementedError


# =========================================================
# Validate Middleware
# =========================================================

class ValidateMiddleware(
    InboundMiddleware
):

    async def process(
        self,
        ctx: InboundContext,
        next_call,
    ) -> None:

        if not isinstance(
            ctx.packet,
            TransportPacket,
        ):
            raise MiddlewareExecutionError(
                "Invalid transport packet."
            )

        await next_call()


# =========================================================
# Session Middleware
# =========================================================

class SessionMiddleware(
    InboundMiddleware
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
        ctx: InboundContext,
        next_call,
    ) -> None:

        session = (
            self.session_service.find_session_by_peer(
                ctx.packet.sender_peer_id
            )
        )

        ctx.session = session

        await next_call()


# =========================================================
# Decrypt Middleware
# =========================================================

class DecryptMiddleware(
    InboundMiddleware
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
        ctx: InboundContext,
        next_call,
    ) -> None:

        packet = ctx.packet

        if (
            packet.packet_type
            != PacketType.MESSAGE
        ):
            await next_call()
            return

        try:

            result = (
                self.protocol_service.receive_message(
                    receiver_profile=(
                        ctx.receiver_profile
                    ),

                    envelope=packet.payload,
                )
            )

            ctx.protocol_result = result

            ctx.verified = bool(
                result.get(
                    "verified",
                    False,
                )
            )

            plaintext = result.get(
                "plaintext"
            )

            if plaintext:
                ctx.plaintext = plaintext

        except (
            ProtocolReplayError,
            ProtocolSignatureError,
            ProtocolDecryptError,
        ) as exc:

            ctx.rejected = True

            raise MiddlewareExecutionError(
                str(exc)
            ) from exc

        await next_call()


# =========================================================
# Delivery Middleware
# =========================================================

class DeliveryMiddleware(
    InboundMiddleware
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
        ctx: InboundContext,
        next_call,
    ) -> None:

        self.delivery_service.mark_delivered(
            ctx.packet.packet_id
        )

        await next_call()


# =========================================================
# ACK Middleware
# =========================================================

class AckMiddleware(
    InboundMiddleware
):

    def __init__(
        self,
        ack_service: AckService,
    ) -> None:

        self.ack_service = (
            ack_service
        )

    async def process(
        self,
        ctx: InboundContext,
        next_call,
    ) -> None:

        packet = ctx.packet

        if packet_requires_ack(
            packet.packet_type
        ):
            self.ack_service.register_inbound_packet(
                packet.packet_id
            )

        await next_call()


# =========================================================
# Store Middleware
# =========================================================

class StoreMiddleware(
    InboundMiddleware
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
        ctx: InboundContext,
        next_call,
    ) -> None:

        if ctx.plaintext:

            self.message_store.store_inbound_message(
                sender_peer_id=(
                    ctx.packet.sender_peer_id
                ),

                receiver_peer_id=(
                    ctx.packet.receiver_peer_id
                ),

                packet_id=(
                    ctx.packet.packet_id
                ),

                plaintext=ctx.plaintext,

                metadata=ctx.metadata,
            )

        await next_call()


# =========================================================
# Event Middleware
# =========================================================

class EventMiddleware(
    InboundMiddleware
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
        ctx: InboundContext,
        next_call,
    ) -> None:

        await next_call()

        event = TransportEvent(
            event_type=(
                TransportEventType.PACKET_RECEIVED
            ),

            peer_id=(
                ctx.packet.sender_peer_id
            ),

            packet_id=(
                ctx.packet.packet_id
            ),

            metadata={
                "packet_type":
                    str(
                        ctx.packet.packet_type
                    ),

                "verified":
                    ctx.verified,

                "plaintext":
                    ctx.plaintext,
            },
        )

        await self.emit_callback(
            event
        )


# =========================================================
# Inbound Pipeline
# =========================================================

class InboundPipeline:
    """
    Middleware-based inbound pipeline.
    """

    def __init__(
        self,
        *,
        protocol_service: ProtocolService,
        session_service: SessionService,
        delivery_service: DeliveryService,
        ack_service: AckService,
        message_store: MessageStore,

        emit_event: Callable[
            [TransportEvent],
            Awaitable[None],
        ],
    ) -> None:

        self._logger = logging.getLogger(
            self.__class__.__name__
        )

        self.middlewares: List[
            InboundMiddleware
        ] = [

            ValidateMiddleware(),

            SessionMiddleware(
                session_service
            ),

            DecryptMiddleware(
                protocol_service
            ),

            DeliveryMiddleware(
                delivery_service
            ),

            AckMiddleware(
                ack_service
            ),

            StoreMiddleware(
                message_store
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
        packet: TransportPacket,
        receiver_profile: Optional[
            dict
        ] = None,
    ) -> InboundContext:

        ctx = InboundContext(
            packet=packet,
            receiver_profile=(
                receiver_profile
            ),
        )

        await self._execute_chain(
            ctx,
            0,
        )

        return ctx

    # =====================================================
    # Internal Chain
    # =====================================================

    async def _execute_chain(
        self,
        ctx: InboundContext,
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
                "Inbound middleware failed: %s",
                exc,
            )

            raise


__all__ = [

    "InboundPipeline",
    "InboundContext",

    "InboundMiddleware",

    "ValidateMiddleware",
    "SessionMiddleware",
    "DecryptMiddleware",
    "DeliveryMiddleware",
    "AckMiddleware",
    "StoreMiddleware",
    "EventMiddleware",

    "InboundPipelineError",
    "MiddlewareExecutionError",
]
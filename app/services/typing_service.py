from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Set

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

from .event_bus import (
    EventBus,
)


# =========================================================
# Exceptions
# =========================================================

class TypingServiceError(Exception):
    """Base typing service exception."""


class InvalidTypingPacketError(
    TypingServiceError
):
    """Invalid typing packet."""


# =========================================================
# Typing State
# =========================================================

@dataclass(slots=True)
class TypingState:
    """
    Runtime typing state.
    """

    peer_id: str

    is_typing: bool = False

    last_activity: float = field(
        default_factory=time.time
    )

    started_at: float = field(
        default_factory=time.time
    )

    expires_at: float = 0.0


# =========================================================
# Typing Service
# =========================================================

class TypingService:
    """
    Realtime typing indicator service.

    Features
    ------------------------------------------------
    - typing start / stop
    - debounce protection
    - auto timeout stop
    - anti-spam
    - event bus integration
    - transport packet integration
    - lightweight ephemeral packets

    Notes
    ------------------------------------------------
    Typing packets:
    - are NOT encrypted payload messages
    - are NOT persisted
    - are NOT ACKed
    - are NOT queued
    - are realtime ephemeral signals
    """

    # =====================================================
    # Config
    # =====================================================

    DEFAULT_TIMEOUT = 5.0

    DEBOUNCE_WINDOW = 1.5

    CLEANUP_INTERVAL = 1.0

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        local_peer_id: str,
        transport,
        event_bus: EventBus,
        timeout_seconds: float = DEFAULT_TIMEOUT,
    ) -> None:

        self._logger = logging.getLogger(
            self.__class__.__name__
        )

        self.local_peer_id = (
            local_peer_id
        )

        self.transport = transport

        self.event_bus = event_bus

        self.timeout_seconds = (
            timeout_seconds
        )

        # =============================================
        # outbound state
        # =============================================

        self._outbound_states: Dict[
            str,
            TypingState,
        ] = {}

        # =============================================
        # inbound state
        # =============================================

        self._inbound_states: Dict[
            str,
            TypingState,
        ] = {}

        # =============================================
        # background cleanup
        # =============================================

        self._cleanup_task: Optional[
            asyncio.Task
        ] = None

        self._running = False

    # =====================================================
    # Lifecycle
    # =====================================================

    async def start(
        self,
    ) -> None:

        if self._running:
            return

        self._running = True

        self._cleanup_task = (
            asyncio.create_task(
                self._cleanup_loop()
            )
        )

    async def stop(
        self,
    ) -> None:

        self._running = False

        if self._cleanup_task:

            self._cleanup_task.cancel()

            await asyncio.gather(
                self._cleanup_task,
                return_exceptions=True,
            )

            self._cleanup_task = None

    # =====================================================
    # Outbound
    # =====================================================

    async def send_typing_start(
        self,
        peer_id: str,
    ) -> bool:
        """
        Send typing start packet.

        Returns:
            True if packet sent
            False if debounced
        """

        now = time.time()

        state = (
            self._outbound_states.get(
                peer_id
            )
        )

        # =============================================
        # Debounce spam
        # =============================================

        if state and state.is_typing:

            delta = (
                now - state.last_activity
            )

            if (
                delta
                < self.DEBOUNCE_WINDOW
            ):
                return False

        # =============================================
        # Update state
        # =============================================

        self._outbound_states[
            peer_id
        ] = TypingState(
            peer_id=peer_id,
            is_typing=True,
            last_activity=now,
            started_at=now,
            expires_at=(
                now
                + self.timeout_seconds
            ),
        )

        packet = (
            self._build_typing_packet(
                packet_type=(
                    PacketType.TYPING_START
                ),
                receiver_peer_id=peer_id,
            )
        )

        await self.transport.send_packet(
            packet
        )

        await self.event_bus.emit(
            TransportEvent(
                event_type=(
                    TransportEventType
                    .TYPING_STARTED
                ),
                peer_id=peer_id,
                packet_id=packet.packet_id,
                metadata={
                    "direction":
                        "outbound"
                },
            )
        )

        return True

    async def send_typing_stop(
        self,
        peer_id: str,
    ) -> bool:
        """
        Send typing stop packet.
        """

        state = (
            self._outbound_states.get(
                peer_id
            )
        )

        if not state:
            return False

        packet = (
            self._build_typing_packet(
                packet_type=(
                    PacketType.TYPING_STOP
                ),
                receiver_peer_id=peer_id,
            )
        )

        await self.transport.send_packet(
            packet
        )

        self._outbound_states.pop(
            peer_id,
            None,
        )

        await self.event_bus.emit(
            TransportEvent(
                event_type=(
                    TransportEventType
                    .TYPING_STOPPED
                ),
                peer_id=peer_id,
                packet_id=packet.packet_id,
                metadata={
                    "direction":
                        "outbound"
                },
            )
        )

        return True

    # =====================================================
    # Inbound
    # =====================================================

    async def handle_typing_packet(
        self,
        packet: TransportPacket,
    ) -> None:
        """
        Handle inbound typing packet.
        """

        packet_type = (
            packet.packet_type
        )

        if packet_type not in {

            PacketType.TYPING_START,

            PacketType.TYPING_STOP,
        }:
            raise (
                InvalidTypingPacketError(
                    f"Invalid typing packet: "
                    f"{packet_type}"
                )
            )

        peer_id = (
            packet.sender_peer_id
        )

        now = time.time()

        # =============================================
        # Typing start
        # =============================================

        if (
            packet_type
            == PacketType.TYPING_START
        ):

            self._inbound_states[
                peer_id
            ] = TypingState(
                peer_id=peer_id,
                is_typing=True,
                last_activity=now,
                started_at=now,
                expires_at=(
                    now
                    + self.timeout_seconds
                ),
            )

            await self.event_bus.emit(
                TransportEvent(
                    event_type=(
                        TransportEventType
                        .TYPING_STARTED
                    ),
                    peer_id=peer_id,
                    packet_id=(
                        packet.packet_id
                    ),
                    metadata={
                        "direction":
                            "inbound"
                    },
                )
            )

            return

        # =============================================
        # Typing stop
        # =============================================

        self._inbound_states.pop(
            peer_id,
            None,
        )

        await self.event_bus.emit(
            TransportEvent(
                event_type=(
                    TransportEventType
                    .TYPING_STOPPED
                ),
                peer_id=peer_id,
                packet_id=(
                    packet.packet_id
                ),
                metadata={
                    "direction":
                        "inbound"
                },
            )
        )

    # =====================================================
    # Cleanup
    # =====================================================

    async def _cleanup_loop(
        self,
    ) -> None:

        while self._running:

            try:

                await asyncio.sleep(
                    self.CLEANUP_INTERVAL
                )

                await self._cleanup_expired()

            except asyncio.CancelledError:
                break

            except Exception as exc:

                self._logger.exception(
                    "Typing cleanup failed: %s",
                    exc,
                )

    async def _cleanup_expired(
        self,
    ) -> None:

        now = time.time()

        expired_peers = []

        for (
            peer_id,
            state,
        ) in self._inbound_states.items():

            if (
                now
                >= state.expires_at
            ):
                expired_peers.append(
                    peer_id
                )

        for peer_id in expired_peers:

            self._inbound_states.pop(
                peer_id,
                None,
            )

            await self.event_bus.emit(
                TransportEvent(
                    event_type=(
                        TransportEventType
                        .TYPING_STOPPED
                    ),
                    peer_id=peer_id,
                    metadata={
                        "reason":
                            "timeout"
                    },
                )
            )

    # =====================================================
    # Packet Builder
    # =====================================================

    def _build_typing_packet(
        self,
        *,
        packet_type: PacketType,
        receiver_peer_id: str,
    ) -> TransportPacket:

        return TransportPacket(
            packet_type=packet_type,

            sender_peer_id=(
                self.local_peer_id
            ),

            receiver_peer_id=(
                receiver_peer_id
            ),

            payload={
                "typing": True
            },

            metadata={
                "ephemeral": True,
                "requires_ack": False,
                "persist": False,
            },
        )

    # =====================================================
    # State Queries
    # =====================================================

    def is_peer_typing(
        self,
        peer_id: str,
    ) -> bool:

        state = (
            self._inbound_states.get(
                peer_id
            )
        )

        return bool(
            state
            and state.is_typing
        )

    def typing_peers(
        self,
    ) -> Set[str]:

        return set(
            self._inbound_states.keys()
        )

    def inbound_state(
        self,
        peer_id: str,
    ) -> Optional[TypingState]:

        return (
            self._inbound_states.get(
                peer_id
            )
        )

    def outbound_state(
        self,
        peer_id: str,
    ) -> Optional[TypingState]:

        return (
            self._outbound_states.get(
                peer_id
            )
        )

    # =====================================================
    # Metrics
    # =====================================================

    def metrics(
        self,
    ) -> dict:

        return {

            "inbound_typing":
                len(
                    self._inbound_states
                ),

            "outbound_typing":
                len(
                    self._outbound_states
                ),

            "running":
                self._running,
        }

    # =====================================================
    # Context Manager
    # =====================================================

    async def __aenter__(
        self,
    ) -> "TypingService":

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

    "TypingService",

    "TypingState",

    "TypingServiceError",

    "InvalidTypingPacketError",
]
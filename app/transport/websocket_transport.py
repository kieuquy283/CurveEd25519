from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable, Optional

import websockets
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
)

from .transport_packet import (
    TransportPacket,
    TransportPacketType,
    InvalidTransportPacketError,
)


# =========================================================
# Exceptions
# =========================================================

class WebSocketTransportError(
    Exception
):
    """Base transport exception."""


class TransportDisconnectedError(
    WebSocketTransportError
):
    """Transport disconnected."""


class PacketSendError(
    WebSocketTransportError
):
    """Packet send failed."""


class PacketReceiveError(
    WebSocketTransportError
):
    """Packet receive failed."""


# =========================================================
# Connection State
# =========================================================

class ConnectionState(str, Enum):

    DISCONNECTED = "disconnected"

    CONNECTING = "connecting"

    CONNECTED = "connected"

    RECONNECTING = "reconnecting"

    CLOSED = "closed"


# =========================================================
# Transport Config
# =========================================================

@dataclass(slots=True)
class WebSocketTransportConfig:

    url: str

    heartbeat_interval: int = 15

    reconnect_interval: int = 5

    reconnect_max_attempts: int = 10

    connect_timeout: int = 10

    receive_timeout: int = 60

    max_message_size: int = 10 * 1024 * 1024

    auto_reconnect: bool = True


# =========================================================
# WebSocket Transport
# =========================================================

class WebSocketTransport:
    """
    Async secure transport runtime.

    Responsibilities
    -------------------------------------------------
    - websocket communication
    - packet send/receive
    - heartbeat
    - reconnect
    - async runtime
    - event dispatch
    - transport reliability

    Transport Layer:
    -------------------------------------------------
    DeliveryService
        ↓
    TransportPacket
        ↓
    WebSocketTransport
        ↓
    WebSocket Network
    """

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        config: WebSocketTransportConfig,
    ) -> None:

        self.config = config

        self.state = (
            ConnectionState.DISCONNECTED
        )

        self.websocket: Optional[
            WebSocketClientProtocol
        ] = None

        self.logger = logging.getLogger(
            self.__class__.__name__
        )

        self._running = False

        self._receive_task: (
            asyncio.Task | None
        ) = None

        self._heartbeat_task: (
            asyncio.Task | None
        ) = None

        self._reconnect_task: (
            asyncio.Task | None
        ) = None

        self._packet_handler: Optional[
            Callable[
                [TransportPacket],
                Awaitable[None],
            ]
        ] = None

        self._disconnect_handler: Optional[
            Callable[[], Awaitable[None]]
        ] = None

        self._connect_handler: Optional[
            Callable[[], Awaitable[None]]
        ] = None

        self._last_pong = time.time()

        self._reconnect_attempts = 0

        self._send_lock = asyncio.Lock()

    # =====================================================
    # Connection Lifecycle
    # =====================================================

    async def connect(self) -> None:

        if (
            self.state
            == ConnectionState.CONNECTED
        ):
            return

        self.state = (
            ConnectionState.CONNECTING
        )

        try:

            self.websocket = (
                await websockets.connect(
                    self.config.url,

                    open_timeout=(
                        self.config
                        .connect_timeout
                    ),

                    max_size=(
                        self.config
                        .max_message_size
                    ),
                )
            )

            self.state = (
                ConnectionState.CONNECTED
            )

            self._running = True

            self._reconnect_attempts = 0

            self.logger.info(
                "Connected to %s",
                self.config.url,
            )

            if (
                self._connect_handler
                is not None
            ):
                await (
                    self._connect_handler()
                )

            self._receive_task = (
                asyncio.create_task(
                    self._receive_loop()
                )
            )

            self._heartbeat_task = (
                asyncio.create_task(
                    self._heartbeat_loop()
                )
            )

        except Exception as exc:

            self.state = (
                ConnectionState.DISCONNECTED
            )

            raise (
                WebSocketTransportError(
                    f"Connection failed: "
                    f"{exc}"
                )
            ) from exc

    async def disconnect(
        self,
    ) -> None:

        self._running = False

        self.state = (
            ConnectionState.CLOSED
        )

        try:

            if (
                self._receive_task
            ):
                self._receive_task.cancel()

            if (
                self._heartbeat_task
            ):
                self._heartbeat_task.cancel()

            if (
                self.websocket
                is not None
            ):
                await self.websocket.close()

        finally:

            self.websocket = None

            self.logger.info(
                "Transport disconnected."
            )

    # =====================================================
    # Send Packet
    # =====================================================

    async def send_packet(
        self,
        packet: TransportPacket,
    ) -> None:

        if (
            self.websocket is None
            or self.state
            != ConnectionState.CONNECTED
        ):
            raise (
                TransportDisconnectedError(
                    "Transport disconnected."
                )
            )

        try:

            packet.validate()

            raw = packet.to_json()

            async with self._send_lock:

                await self.websocket.send(
                    raw
                )

        except Exception as exc:

            raise PacketSendError(
                str(exc)
            ) from exc

    # =====================================================
    # Receive Loop
    # =====================================================

    async def _receive_loop(
        self,
    ) -> None:

        assert (
            self.websocket
            is not None
        )

        while self._running:

            try:

                raw = await asyncio.wait_for(
                    self.websocket.recv(),

                    timeout=(
                        self.config
                        .receive_timeout
                    ),
                )

                packet = (
                    TransportPacket
                    .from_json(raw)
                )

                await self._handle_packet(
                    packet
                )

            except asyncio.TimeoutError:

                self.logger.warning(
                    "Receive timeout."
                )

            except (
                ConnectionClosed,
                ConnectionClosedError,
            ):

                self.logger.warning(
                    "WebSocket closed."
                )

                await self._handle_disconnect()

                return

            except (
                InvalidTransportPacketError
            ) as exc:

                self.logger.warning(
                    "Invalid packet: %s",
                    exc,
                )

            except Exception as exc:

                self.logger.exception(
                    "Receive loop error: %s",
                    exc,
                )

    # =====================================================
    # Packet Handling
    # =====================================================

    async def _handle_packet(
        self,
        packet: TransportPacket,
    ) -> None:

        # =============================================
        # Heartbeat
        # =============================================

        if packet.is_ping:

            pong = (
                TransportPacket
                .build_pong_packet(
                    sender_id=(
                        packet.receiver_id
                    ),

                    receiver_id=(
                        packet.sender_id
                    ),
                )
            )

            await self.send_packet(
                pong
            )

            return

        if packet.is_pong:

            self._last_pong = (
                time.time()
            )

            return

        # =============================================
        # App packet dispatch
        # =============================================

        if (
            self._packet_handler
            is not None
        ):
            await self._packet_handler(
                packet
            )

    # =====================================================
    # Heartbeat
    # =====================================================

    async def _heartbeat_loop(
        self,
    ) -> None:

        while self._running:

            try:

                if (
                    self.state
                    != ConnectionState.CONNECTED
                ):
                    return

                ping = (
                    TransportPacket
                    .build_ping_packet(
                        sender_id="client",
                        receiver_id="server",
                    )
                )

                await self.send_packet(
                    ping
                )

                await asyncio.sleep(
                    self.config
                    .heartbeat_interval
                )

            except Exception as exc:

                self.logger.warning(
                    "Heartbeat failure: %s",
                    exc,
                )

                await self._handle_disconnect()

                return

    # =====================================================
    # Reconnect
    # =====================================================

    async def _handle_disconnect(
        self,
    ) -> None:

        if not self._running:
            return

        self.state = (
            ConnectionState.DISCONNECTED
        )

        if (
            self._disconnect_handler
            is not None
        ):
            await (
                self._disconnect_handler()
            )

        if (
            self.config.auto_reconnect
        ):
            await self._reconnect()

    async def _reconnect(
        self,
    ) -> None:

        if (
            self._reconnect_attempts
            >= self.config
            .reconnect_max_attempts
        ):

            self.logger.error(
                "Reconnect limit reached."
            )

            return

        self.state = (
            ConnectionState.RECONNECTING
        )

        self._reconnect_attempts += 1

        self.logger.warning(
            "Reconnect attempt %d",
            self._reconnect_attempts,
        )

        await asyncio.sleep(
            self.config
            .reconnect_interval
        )

        try:

            await self.connect()

        except Exception as exc:

            self.logger.warning(
                "Reconnect failed: %s",
                exc,
            )

            await self._reconnect()

    # =====================================================
    # Event Handlers
    # =====================================================

    def on_packet(
        self,
        handler: Callable[
            [TransportPacket],
            Awaitable[None],
        ],
    ) -> None:

        self._packet_handler = (
            handler
        )

    def on_disconnect(
        self,
        handler: Callable[
            [],
            Awaitable[None],
        ],
    ) -> None:

        self._disconnect_handler = (
            handler
        )

    def on_connect(
        self,
        handler: Callable[
            [],
            Awaitable[None],
        ],
    ) -> None:

        self._connect_handler = (
            handler
        )

    # =====================================================
    # Helpers
    # =====================================================

    @property
    def connected(self) -> bool:

        return (
            self.state
            == ConnectionState.CONNECTED
        )

    @property
    def disconnected(
        self,
    ) -> bool:

        return (
            self.state
            == ConnectionState.DISCONNECTED
        )

    @property
    def reconnecting(
        self,
    ) -> bool:

        return (
            self.state
            == ConnectionState.RECONNECTING
        )

    # =====================================================
    # Context Manager
    # =====================================================

    async def __aenter__(
        self,
    ) -> "WebSocketTransport":

        await self.connect()

        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        tb,
    ) -> None:

        await self.disconnect()
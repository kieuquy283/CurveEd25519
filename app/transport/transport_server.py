from __future__ import annotations

import asyncio
import json
import logging
import signal
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Optional, Set

import websockets
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
)
from websockets.server import (
    WebSocketServerProtocol,
)

from .transport_packet import (
    InvalidTransportPacketError,
    TransportPacket,
    TransportPacketType,
)


# =========================================================
# Exceptions
# =========================================================

class TransportServerError(
    Exception
):
    """Base transport server error."""


class ClientAlreadyConnectedError(
    TransportServerError
):
    """Duplicate client connection."""


class ClientNotConnectedError(
    TransportServerError
):
    """Client not connected."""


# =========================================================
# Config
# =========================================================

@dataclass(slots=True)
class TransportServerConfig:

    host: str = "0.0.0.0"

    port: int = 8765

    max_message_size: int = (
        10 * 1024 * 1024
    )

    heartbeat_interval: int = 15

    client_timeout: int = 60

    cleanup_interval: int = 30

    enable_logging: bool = True


# =========================================================
# Client Session
# =========================================================

@dataclass(slots=True)
class ClientSession:

    client_id: str

    websocket: WebSocketServerProtocol

    connected_at: float

    last_seen_at: float

    metadata: dict


# =========================================================
# Transport Server
# =========================================================

class TransportServer:
    """
    High-performance websocket transport server.

    Responsibilities
    -------------------------------------------------
    - websocket server runtime
    - client session management
    - packet routing
    - heartbeat monitoring
    - broadcast delivery
    - async event handling
    - client lifecycle

    Architecture
    -------------------------------------------------

        Client
            ↓
        WebSocket
            ↓
        TransportServer
            ↓
        DeliveryService
            ↓
        ProtocolService
    """

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        config: TransportServerConfig,
    ) -> None:

        self.config = config

        self.logger = logging.getLogger(
            self.__class__.__name__
        )

        self.server = None

        self._running = False

        self._clients: Dict[
            str,
            ClientSession,
        ] = {}

        self._packet_handler: Optional[
            Callable[
                [
                    ClientSession,
                    TransportPacket,
                ],
                Awaitable[None],
            ]
        ] = None

        self._connect_handler: Optional[
            Callable[
                [ClientSession],
                Awaitable[None],
            ]
        ] = None

        self._disconnect_handler: Optional[
            Callable[
                [ClientSession],
                Awaitable[None],
            ]
        ] = None

        self._cleanup_task: (
            asyncio.Task | None
        ) = None

        self._send_locks: Dict[
            str,
            asyncio.Lock,
        ] = defaultdict(
            asyncio.Lock
        )

    # =====================================================
    # Server Lifecycle
    # =====================================================

    async def start(self) -> None:

        if self._running:
            return

        self.server = (
            await websockets.serve(
                self._handle_connection,

                host=self.config.host,

                port=self.config.port,

                max_size=(
                    self.config
                    .max_message_size
                ),
            )
        )

        self._running = True

        self.logger.info(
            "Transport server started "
            "on %s:%d",
            self.config.host,
            self.config.port,
        )

        self._cleanup_task = (
            asyncio.create_task(
                self._cleanup_loop()
            )
        )

    async def stop(self) -> None:

        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()

        # Disconnect all clients
        for client_id in list(
            self._clients.keys()
        ):

            try:
                await self.disconnect_client(
                    client_id
                )

            except Exception:
                pass

        if self.server:
            self.server.close()
            await self.server.wait_closed()

        self.logger.info(
            "Transport server stopped."
        )

    # =====================================================
    # Connection Handling
    # =====================================================

    async def _handle_connection(
        self,
        websocket: WebSocketServerProtocol,
    ) -> None:

        client_session = None

        try:

            # =============================================
            # Authentication handshake
            # =============================================

            raw = await asyncio.wait_for(
                websocket.recv(),
                timeout=15,
            )

            packet = (
                TransportPacket
                .from_json(raw)
            )

            if (
                packet.packet_type
                != TransportPacketType.AUTH
            ):
                raise (
                    TransportServerError(
                        "First packet "
                        "must be AUTH."
                    )
                )

            client_id = (
                packet.sender_id
            )

            if client_id in self._clients:
                raise (
                    ClientAlreadyConnectedError(
                        f"Client already connected: "
                        f"{client_id}"
                    )
                )

            # =============================================
            # Register session
            # =============================================

            now = time.time()

            client_session = ClientSession(
                client_id=client_id,

                websocket=websocket,

                connected_at=now,

                last_seen_at=now,

                metadata=packet.payload,
            )

            self._clients[
                client_id
            ] = client_session

            self.logger.info(
                "Client connected: %s",
                client_id,
            )

            # =============================================
            # Notify app layer
            # =============================================

            if (
                self._connect_handler
                is not None
            ):
                await (
                    self._connect_handler(
                        client_session
                    )
                )

            # =============================================
            # Main receive loop
            # =============================================

            await self._client_receive_loop(
                client_session
            )

        except (
            ConnectionClosed,
            ConnectionClosedError,
        ):
            pass

        except Exception as exc:

            self.logger.exception(
                "Connection error: %s",
                exc,
            )

        finally:

            if client_session:
                await self._cleanup_client(
                    client_session
                )

    # =====================================================
    # Receive Loop
    # =====================================================

    async def _client_receive_loop(
        self,
        session: ClientSession,
    ) -> None:

        websocket = (
            session.websocket
        )

        while self._running:

            try:

                raw = await asyncio.wait_for(
                    websocket.recv(),

                    timeout=(
                        self.config
                        .client_timeout
                    ),
                )

                session.last_seen_at = (
                    time.time()
                )

                packet = (
                    TransportPacket
                    .from_json(raw)
                )

                await self._handle_packet(
                    session,
                    packet,
                )

            except asyncio.TimeoutError:

                self.logger.warning(
                    "Client timeout: %s",
                    session.client_id,
                )

                return

            except (
                ConnectionClosed,
                ConnectionClosedError,
            ):
                return

            except (
                InvalidTransportPacketError
            ) as exc:

                self.logger.warning(
                    "Invalid packet from %s: %s",
                    session.client_id,
                    exc,
                )

            except Exception as exc:

                self.logger.exception(
                    "Receive loop failure: %s",
                    exc,
                )

    # =====================================================
    # Packet Routing
    # =====================================================

    async def _handle_packet(
        self,
        session: ClientSession,
        packet: TransportPacket,
    ) -> None:

        # =============================================
        # Heartbeat
        # =============================================

        if packet.is_ping:

            pong = (
                TransportPacket
                .build_pong_packet(
                    sender_id="server",
                    receiver_id=(
                        session.client_id
                    ),
                )
            )

            await self.send_packet(
                session.client_id,
                pong,
            )

            return

        if packet.is_pong:
            return

        # =============================================
        # Direct routing
        # =============================================

        if (
            packet.receiver_id
            and packet.receiver_id
            in self._clients
        ):

            await self.send_packet(
                packet.receiver_id,
                packet,
            )

        # =============================================
        # App callback
        # =============================================

        if (
            self._packet_handler
            is not None
        ):
            await self._packet_handler(
                session,
                packet,
            )

    # =====================================================
    # Send Packet
    # =====================================================

    async def send_packet(
        self,
        client_id: str,
        packet: TransportPacket,
    ) -> None:

        session = (
            self._clients.get(
                client_id
            )
        )

        if session is None:
            raise (
                ClientNotConnectedError(
                    f"Client not connected: "
                    f"{client_id}"
                )
            )

        packet.validate()

        raw = packet.to_json()

        lock = self._send_locks[
            client_id
        ]

        async with lock:

            await session.websocket.send(
                raw
            )

    # =====================================================
    # Broadcast
    # =====================================================

    async def broadcast_packet(
        self,
        packet: TransportPacket,
        *,
        exclude: Optional[
            Set[str]
        ] = None,
    ) -> None:

        exclude = exclude or set()

        tasks = []

        for client_id in (
            self._clients.keys()
        ):

            if client_id in exclude:
                continue

            tasks.append(
                self.send_packet(
                    client_id,
                    packet,
                )
            )

        if tasks:
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

    # =====================================================
    # Client Management
    # =====================================================

    async def disconnect_client(
        self,
        client_id: str,
    ) -> None:

        session = (
            self._clients.get(
                client_id
            )
        )

        if session is None:
            return

        try:
            await (
                session.websocket.close()
            )

        finally:
            await self._cleanup_client(
                session
            )

    async def _cleanup_client(
        self,
        session: ClientSession,
    ) -> None:

        self._clients.pop(
            session.client_id,
            None,
        )

        self._send_locks.pop(
            session.client_id,
            None,
        )

        self.logger.info(
            "Client disconnected: %s",
            session.client_id,
        )

        if (
            self._disconnect_handler
            is not None
        ):
            await (
                self._disconnect_handler(
                    session
                )
            )

    # =====================================================
    # Cleanup Loop
    # =====================================================

    async def _cleanup_loop(
        self,
    ) -> None:

        while self._running:

            try:

                await asyncio.sleep(
                    self.config
                    .cleanup_interval
                )

                now = time.time()

                stale_clients = []

                for (
                    client_id,
                    session,
                ) in self._clients.items():

                    elapsed = (
                        now
                        - session.last_seen_at
                    )

                    if (
                        elapsed
                        > self.config
                        .client_timeout
                    ):
                        stale_clients.append(
                            client_id
                        )

                for client_id in (
                    stale_clients
                ):

                    self.logger.warning(
                        "Removing stale client: %s",
                        client_id,
                    )

                    await self.disconnect_client(
                        client_id
                    )

            except asyncio.CancelledError:
                return

            except Exception as exc:

                self.logger.exception(
                    "Cleanup loop failure: %s",
                    exc,
                )

    # =====================================================
    # Event Handlers
    # =====================================================

    def on_packet(
        self,
        handler: Callable[
            [
                ClientSession,
                TransportPacket,
            ],
            Awaitable[None],
        ],
    ) -> None:

        self._packet_handler = (
            handler
        )

    def on_connect(
        self,
        handler: Callable[
            [ClientSession],
            Awaitable[None],
        ],
    ) -> None:

        self._connect_handler = (
            handler
        )

    def on_disconnect(
        self,
        handler: Callable[
            [ClientSession],
            Awaitable[None],
        ],
    ) -> None:

        self._disconnect_handler = (
            handler
        )

    # =====================================================
    # Metrics
    # =====================================================

    @property
    def connected_clients(
        self,
    ) -> int:

        return len(self._clients)

    def get_client(
        self,
        client_id: str,
    ) -> Optional[ClientSession]:

        return self._clients.get(
            client_id
        )

    def list_clients(
        self,
    ) -> list[str]:

        return list(
            self._clients.keys()
        )

    # =====================================================
    # Run Helper
    # =====================================================

    async def run_forever(
        self,
    ) -> None:

        await self.start()

        stop_event = asyncio.Event()

        loop = asyncio.get_running_loop()

        for sig in (
            signal.SIGINT,
            signal.SIGTERM,
        ):
            loop.add_signal_handler(
                sig,
                stop_event.set,
            )

        await stop_event.wait()

        await self.stop()

    # =====================================================
    # Context Manager
    # =====================================================

    async def __aenter__(
        self,
    ) -> "TransportServer":

        await self.start()

        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        tb,
    ) -> None:

        await self.stop()
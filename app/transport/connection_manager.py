from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, Dict, List, Optional, Set

from .peer_registry import (
    PeerRegistry,
    PeerRecord,
)

from .transport_packet import (
    TransportPacket,
)

from .websocket_transport import (
    WebSocketTransport,
)

from .transport_server import (
    TransportServer,
    ClientSession,
)


# =========================================================
# Exceptions
# =========================================================

class ConnectionManagerError(
    Exception
):
    """Base connection manager error."""


class PeerOfflineError(
    ConnectionManagerError
):
    """Peer offline."""


class SessionNotFoundError(
    ConnectionManagerError
):
    """Connection session missing."""


# =========================================================
# Connection State
# =========================================================

class PeerConnectionState(
    str,
    Enum,
):

    OFFLINE = "offline"

    CONNECTING = "connecting"

    ONLINE = "online"

    DISCONNECTED = "disconnected"

    BLOCKED = "blocked"


# =========================================================
# Peer Connection
# =========================================================

@dataclass(slots=True)
class PeerConnection:

    peer_id: str

    state: PeerConnectionState

    connected_at: float

    last_seen_at: float

    transport_id: str

    metadata: dict = field(
        default_factory=dict
    )

    latency_ms: Optional[
        float
    ] = None

    active_sessions: int = 0


# =========================================================
# Connection Manager
# =========================================================

class ConnectionManager:
    """
    High-level peer connection orchestration.

    Responsibilities
    ------------------------------------------------
    - peer online/offline tracking
    - transport session coordination
    - connection lifecycle
    - peer discovery
    - transport abstraction
    - connection events
    - routing helpers

    Architecture
    ------------------------------------------------

        UI / Messaging Layer
                ↓
        ConnectionManager
                ↓
        Transport Layer
                ↓
        WebSocketTransport
    """

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        peer_registry: PeerRegistry,
    ) -> None:

        self.peer_registry = (
            peer_registry
        )

        self.logger = logging.getLogger(
            self.__class__.__name__
        )

        self._connections: Dict[
            str,
            PeerConnection,
        ] = {}

        self._transports: Dict[
            str,
            WebSocketTransport,
        ] = {}

        self._servers: Dict[
            str,
            TransportServer,
        ] = {}

        self._lock = asyncio.Lock()

        # =================================================
        # Event handlers
        # =================================================

        self._peer_connected_handler: Optional[
            Callable[
                [PeerConnection],
                Awaitable[None],
            ]
        ] = None

        self._peer_disconnected_handler: Optional[
            Callable[
                [PeerConnection],
                Awaitable[None],
            ]
        ] = None

        self._packet_handler: Optional[
            Callable[
                [TransportPacket],
                Awaitable[None],
            ]
        ] = None

    # =====================================================
    # Register Transport
    # =====================================================

    def register_transport(
        self,
        *,
        transport_id: str,
        transport: WebSocketTransport,
    ) -> None:

        self._transports[
            transport_id
        ] = transport

        transport.on_packet(
            self._handle_packet
        )

        transport.on_connect(
            lambda: self._handle_transport_connected(
                transport_id
            )
        )

        transport.on_disconnect(
            lambda: self._handle_transport_disconnected(
                transport_id
            )
        )

    # =====================================================
    # Register Server
    # =====================================================

    def register_server(
        self,
        *,
        server_id: str,
        server: TransportServer,
    ) -> None:

        self._servers[
            server_id
        ] = server

        server.on_connect(
            self._handle_client_connected
        )

        server.on_disconnect(
            self._handle_client_disconnected
        )

        server.on_packet(
            self._handle_server_packet
        )

    # =====================================================
    # Peer State Management
    # =====================================================

    async def mark_peer_online(
        self,
        *,
        peer_id: str,
        transport_id: str,
        metadata: Optional[
            dict
        ] = None,
    ) -> PeerConnection:

        async with self._lock:

            now = time.time()

            connection = (
                PeerConnection(
                    peer_id=peer_id,

                    state=(
                        PeerConnectionState
                        .ONLINE
                    ),

                    connected_at=now,

                    last_seen_at=now,

                    transport_id=(
                        transport_id
                    ),

                    metadata=(
                        metadata or {}
                    ),
                )
            )

            self._connections[
                peer_id
            ] = connection

            try:
                self.peer_registry.update_last_seen(
                    peer_id
                )
            except Exception:
                pass

            self.logger.info(
                "Peer online: %s",
                peer_id,
            )

            if (
                self
                ._peer_connected_handler
                is not None
            ):
                await (
                    self
                    ._peer_connected_handler(
                        connection
                    )
                )

            return connection

    async def mark_peer_offline(
        self,
        peer_id: str,
    ) -> None:

        async with self._lock:

            connection = (
                self._connections.get(
                    peer_id
                )
            )

            if connection is None:
                return

            connection.state = (
                PeerConnectionState
                .OFFLINE
            )

            self.logger.info(
                "Peer offline: %s",
                peer_id,
            )

            if (
                self
                ._peer_disconnected_handler
                is not None
            ):
                await (
                    self
                    ._peer_disconnected_handler(
                        connection
                    )
                )

    # =====================================================
    # Packet Routing
    # =====================================================

    async def send_packet(
        self,
        *,
        peer_id: str,
        packet: TransportPacket,
    ) -> None:

        connection = (
            self._connections.get(
                peer_id
            )
        )

        if (
            connection is None
            or connection.state
            != PeerConnectionState.ONLINE
        ):
            raise (
                PeerOfflineError(
                    peer_id
                )
            )

        transport = (
            self._transports.get(
                connection.transport_id
            )
        )

        if transport is None:
            raise (
                SessionNotFoundError(
                    connection.transport_id
                )
            )

        await transport.send_packet(
            packet
        )

    async def broadcast_packet(
        self,
        packet: TransportPacket,
        *,
        exclude_peers: Optional[
            Set[str]
        ] = None,
    ) -> None:

        exclude_peers = (
            exclude_peers or set()
        )

        tasks = []

        for (
            peer_id,
            connection,
        ) in self._connections.items():

            if (
                connection.state
                != PeerConnectionState.ONLINE
            ):
                continue

            if peer_id in exclude_peers:
                continue

            tasks.append(
                self.send_packet(
                    peer_id=peer_id,
                    packet=packet,
                )
            )

        if tasks:

            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

    # =====================================================
    # Transport Events
    # =====================================================

    async def _handle_transport_connected(
        self,
        transport_id: str,
    ) -> None:

        self.logger.info(
            "Transport connected: %s",
            transport_id,
        )

    async def _handle_transport_disconnected(
        self,
        transport_id: str,
    ) -> None:

        self.logger.warning(
            "Transport disconnected: %s",
            transport_id,
        )

        affected = []

        for (
            peer_id,
            connection,
        ) in self._connections.items():

            if (
                connection.transport_id
                == transport_id
            ):
                affected.append(
                    peer_id
                )

        for peer_id in affected:
            await self.mark_peer_offline(
                peer_id
            )

    # =====================================================
    # Server Events
    # =====================================================

    async def _handle_client_connected(
        self,
        session: ClientSession,
    ) -> None:

        await self.mark_peer_online(
            peer_id=session.client_id,

            transport_id="server",

            metadata=session.metadata,
        )

    async def _handle_client_disconnected(
        self,
        session: ClientSession,
    ) -> None:

        await self.mark_peer_offline(
            session.client_id
        )

    async def _handle_server_packet(
        self,
        session: ClientSession,
        packet: TransportPacket,
    ) -> None:

        await self._handle_packet(
            packet
        )

    async def _handle_packet(
        self,
        packet: TransportPacket,
    ) -> None:

        if (
            self._packet_handler
            is not None
        ):
            await self._packet_handler(
                packet
            )

    # =====================================================
    # Presence
    # =====================================================

    def is_peer_online(
        self,
        peer_id: str,
    ) -> bool:

        connection = (
            self._connections.get(
                peer_id
            )
        )

        if connection is None:
            return False

        return (
            connection.state
            == PeerConnectionState.ONLINE
        )

    def get_peer_connection(
        self,
        peer_id: str,
    ) -> Optional[
        PeerConnection
    ]:

        return self._connections.get(
            peer_id
        )

    def list_online_peers(
        self,
    ) -> List[str]:

        return [
            peer_id

            for (
                peer_id,
                connection,
            ) in self._connections.items()

            if (
                connection.state
                == PeerConnectionState.ONLINE
            )
        ]

    def count_online_peers(
        self,
    ) -> int:

        return len(
            self.list_online_peers()
        )

    # =====================================================
    # Peer Validation
    # =====================================================

    def validate_peer_trust(
        self,
        peer_id: str,
    ) -> bool:

        try:

            peer = (
                self.peer_registry
                .get_peer(peer_id)
            )

            return (
                peer.is_trusted
                and not peer.is_blocked
            )

        except Exception:
            return False

    # =====================================================
    # Disconnect
    # =====================================================

    async def disconnect_peer(
        self,
        peer_id: str,
    ) -> None:

        connection = (
            self._connections.get(
                peer_id
            )
        )

        if connection is None:
            return

        transport = (
            self._transports.get(
                connection.transport_id
            )
        )

        if transport:

            try:
                await (
                    transport.disconnect()
                )
            except Exception:
                pass

        await self.mark_peer_offline(
            peer_id
        )

    # =====================================================
    # Event Registration
    # =====================================================

    def on_peer_connected(
        self,
        handler: Callable[
            [PeerConnection],
            Awaitable[None],
        ],
    ) -> None:

        self._peer_connected_handler = (
            handler
        )

    def on_peer_disconnected(
        self,
        handler: Callable[
            [PeerConnection],
            Awaitable[None],
        ],
    ) -> None:

        self._peer_disconnected_handler = (
            handler
        )

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

    # =====================================================
    # Metrics
    # =====================================================

    def stats(
        self,
    ) -> dict:

        return {
            "online_peers": (
                self.count_online_peers()
            ),

            "registered_transports": len(
                self._transports
            ),

            "registered_servers": len(
                self._servers
            ),

            "known_connections": len(
                self._connections
            ),
        }
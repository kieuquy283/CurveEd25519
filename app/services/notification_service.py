from __future__ import annotations

import asyncio
import logging
import platform
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
)

from ..transport.transport_events import (
    TransportEvent,
    TransportEventType,
)

from .event_bus import (
    EventBus,
)


# =========================================================
# Notification Level
# =========================================================

class NotificationLevel(str, Enum):

    INFO = "info"

    SUCCESS = "success"

    WARNING = "warning"

    ERROR = "error"

    MESSAGE = "message"

    SYSTEM = "system"


# =========================================================
# Notification
# =========================================================

@dataclass(slots=True)
class Notification:

    id: str

    title: str

    body: str

    level: NotificationLevel

    created_at: float = field(
        default_factory=time.time
    )

    peer_id: Optional[str] = None

    packet_id: Optional[str] = None

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    read: bool = False

    dismissed: bool = False


# =========================================================
# Exceptions
# =========================================================

class NotificationServiceError(
    Exception
):
    """Base notification service exception."""


# =========================================================
# Notification Service
# =========================================================

class NotificationService:
    """
    Unified notification system.

    Features
    ------------------------------------------------
    - desktop notifications
    - unread tracking
    - sound hooks
    - badge counts
    - event bus integration
    - toast notifications
    - notification history
    - mute support
    - priority levels
    """

    MAX_HISTORY = 1000

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        event_bus: EventBus,
        enable_desktop: bool = True,
        enable_sound: bool = True,
        enable_badges: bool = True,
    ) -> None:

        self._logger = logging.getLogger(
            self.__class__.__name__
        )

        self.event_bus = event_bus

        self.enable_desktop = (
            enable_desktop
        )

        self.enable_sound = (
            enable_sound
        )

        self.enable_badges = (
            enable_badges
        )

        # =============================================
        # State
        # =============================================

        self._notifications: List[
            Notification
        ] = []

        self._unread_count = 0

        self._muted_peers: set[str] = set()

        self._callbacks: List[
            Callable[
                [Notification],
                Awaitable[None] | None,
            ]
        ] = []

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

        self._subscribe_events()

    async def stop(
        self,
    ) -> None:

        self._running = False

    # =====================================================
    # Event Subscription
    # =====================================================

    def _subscribe_events(
        self,
    ) -> None:

        self.event_bus.subscribe(
            TransportEventType.MESSAGE_RECEIVED,
            self._handle_message_received,
        )

        self.event_bus.subscribe(
            TransportEventType.MESSAGE_SENT,
            self._handle_message_sent,
        )

        self.event_bus.subscribe(
            TransportEventType.ERROR,
            self._handle_error,
        )

        self.event_bus.subscribe(
            TransportEventType.TYPING_STARTED,
            self._handle_typing_started,
        )

    # =====================================================
    # Event Handlers
    # =====================================================

    async def _handle_message_received(
        self,
        event: TransportEvent,
    ) -> None:

        peer_id = event.peer_id

        if (
            peer_id
            and peer_id
            in self._muted_peers
        ):
            return

        metadata = (
            event.metadata or {}
        )

        sender = (
            metadata.get(
                "sender_name"
            )
            or peer_id
            or "Unknown"
        )

        plaintext = (
            metadata.get(
                "plaintext"
            )
            or "New message"
        )

        notification = (
            await self.notify(
                title=sender,
                body=plaintext,
                level=(
                    NotificationLevel
                    .MESSAGE
                ),
                peer_id=peer_id,
                packet_id=(
                    event.packet_id
                ),
                metadata=metadata,
            )
        )

        await self._play_sound(
            "message"
        )

        await self._update_badge()

    async def _handle_message_sent(
        self,
        event: TransportEvent,
    ) -> None:

        # optional outbound toast
        pass

    async def _handle_error(
        self,
        event: TransportEvent,
    ) -> None:

        metadata = (
            event.metadata or {}
        )

        error_message = (
            metadata.get(
                "error"
            )
            or "Unknown error"
        )

        await self.notify(
            title="Error",
            body=error_message,
            level=(
                NotificationLevel.ERROR
            ),
            packet_id=(
                event.packet_id
            ),
            metadata=metadata,
        )

    async def _handle_typing_started(
        self,
        event: TransportEvent,
    ) -> None:

        metadata = (
            event.metadata or {}
        )

        direction = metadata.get(
            "direction"
        )

        if direction != "inbound":
            return

        peer = (
            event.peer_id
            or "Unknown"
        )

        await self._emit_to_callbacks(
            Notification(
                id=f"typing-{peer}",

                title="Typing",

                body=f"{peer} is typing...",

                level=(
                    NotificationLevel.INFO
                ),

                peer_id=peer,

                metadata={
                    "ephemeral": True
                },
            )
        )

    # =====================================================
    # Notify
    # =====================================================

    async def notify(
        self,
        *,
        title: str,
        body: str,
        level: NotificationLevel,
        peer_id: Optional[
            str
        ] = None,
        packet_id: Optional[
            str
        ] = None,
        metadata: Optional[
            dict
        ] = None,
    ) -> Notification:

        notification = Notification(
            id=(
                f"notif-{time.time_ns()}"
            ),

            title=title,

            body=body,

            level=level,

            peer_id=peer_id,

            packet_id=packet_id,

            metadata=(
                metadata or {}
            ),
        )

        self._notifications.append(
            notification
        )

        self._trim_history()

        self._unread_count += 1

        # =============================================
        # Desktop notification
        # =============================================

        if self.enable_desktop:

            await self._show_desktop_notification(
                notification
            )

        # =============================================
        # Emit to listeners
        # =============================================

        await self._emit_to_callbacks(
            notification
        )

        return notification

    # =====================================================
    # Desktop Notifications
    # =====================================================

    async def _show_desktop_notification(
        self,
        notification: Notification,
    ) -> None:

        try:

            system = (
                platform.system()
                .lower()
            )

            # =========================================
            # Linux
            # =========================================

            if system == "linux":

                proc = await asyncio.create_subprocess_exec(
                    "notify-send",
                    notification.title,
                    notification.body,
                )

                await proc.communicate()

            # =========================================
            # macOS
            # =========================================

            elif system == "darwin":

                script = (
                    f'display notification '
                    f'"{notification.body}" '
                    f'with title '
                    f'"{notification.title}"'
                )

                proc = await asyncio.create_subprocess_exec(
                    "osascript",
                    "-e",
                    script,
                )

                await proc.communicate()

            # =========================================
            # Windows
            # =========================================

            elif system == "windows":

                # Placeholder
                # Can integrate win10toast later
                pass

        except Exception as exc:

            self._logger.debug(
                "Desktop notification failed: %s",
                exc,
            )

    # =====================================================
    # Sound
    # =====================================================

    async def _play_sound(
        self,
        sound_type: str,
    ) -> None:

        if not self.enable_sound:
            return

        try:

            # =========================================
            # simple terminal bell fallback
            # =========================================

            print("\a", end="")

        except Exception:
            pass

    # =====================================================
    # Badge
    # =====================================================

    async def _update_badge(
        self,
    ) -> None:

        if not self.enable_badges:
            return

        # UI frameworks can hook here
        pass

    # =====================================================
    # Notification State
    # =====================================================

    def notifications(
        self,
    ) -> List[Notification]:

        return list(
            self._notifications
        )

    def unread_notifications(
        self,
    ) -> List[Notification]:

        return [

            n for n
            in self._notifications

            if not n.read
        ]

    def unread_count(
        self,
    ) -> int:

        return self._unread_count

    def mark_read(
        self,
        notification_id: str,
    ) -> bool:

        for notification in (
            self._notifications
        ):

            if (
                notification.id
                == notification_id
            ):

                if not notification.read:

                    notification.read = True

                    self._unread_count = max(
                        0,
                        self._unread_count - 1,
                    )

                return True

        return False

    def mark_all_read(
        self,
    ) -> None:

        for notification in (
            self._notifications
        ):
            notification.read = True

        self._unread_count = 0

    def dismiss(
        self,
        notification_id: str,
    ) -> bool:

        for notification in (
            self._notifications
        ):

            if (
                notification.id
                == notification_id
            ):

                notification.dismissed = True

                return True

        return False

    # =====================================================
    # Mute
    # =====================================================

    def mute_peer(
        self,
        peer_id: str,
    ) -> None:

        self._muted_peers.add(
            peer_id
        )

    def unmute_peer(
        self,
        peer_id: str,
    ) -> None:

        self._muted_peers.discard(
            peer_id
        )

    def is_muted(
        self,
        peer_id: str,
    ) -> bool:

        return (
            peer_id
            in self._muted_peers
        )

    # =====================================================
    # UI Hooks
    # =====================================================

    def subscribe(
        self,
        callback,
    ) -> None:

        self._callbacks.append(
            callback
        )

    def unsubscribe(
        self,
        callback,
    ) -> None:

        try:
            self._callbacks.remove(
                callback
            )
        except ValueError:
            pass

    async def _emit_to_callbacks(
        self,
        notification: Notification,
    ) -> None:

        if not self._callbacks:
            return

        await asyncio.gather(
            *[
                self._safe_callback(
                    callback,
                    notification,
                )
                for callback
                in self._callbacks
            ],
            return_exceptions=True,
        )

    async def _safe_callback(
        self,
        callback,
        notification,
    ) -> None:

        try:

            result = callback(
                notification
            )

            if asyncio.iscoroutine(
                result
            ):
                await result

        except Exception as exc:

            self._logger.exception(
                "Notification callback failed: %s",
                exc,
            )

    # =====================================================
    # Helpers
    # =====================================================

    def _trim_history(
        self,
    ) -> None:

        if len(
            self._notifications
        ) <= self.MAX_HISTORY:
            return

        overflow = (
            len(self._notifications)
            - self.MAX_HISTORY
        )

        self._notifications = (
            self._notifications[
                overflow:
            ]
        )

    # =====================================================
    # Metrics
    # =====================================================

    def metrics(
        self,
    ) -> Dict[str, Any]:

        return {

            "notifications":
                len(
                    self._notifications
                ),

            "unread":
                self._unread_count,

            "muted_peers":
                len(
                    self._muted_peers
                ),

            "desktop_enabled":
                self.enable_desktop,

            "sound_enabled":
                self.enable_sound,
        }

    # =====================================================
    # Context Manager
    # =====================================================

    async def __aenter__(
        self,
    ) -> "NotificationService":

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

    "NotificationService",

    "Notification",

    "NotificationLevel",

    "NotificationServiceError",
]
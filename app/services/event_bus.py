from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    DefaultDict,
    Dict,
    List,
    Optional,
    Set,
)

from ..transport.transport_events import (
    TransportEvent,
    TransportEventType,
)


# =========================================================
# Type Aliases
# =========================================================

EventCallback = Callable[
    [TransportEvent],
    Awaitable[None] | None,
]


# =========================================================
# Exceptions
# =========================================================

class EventBusError(Exception):
    """Base event bus exception."""


class EventSubscriptionError(
    EventBusError
):
    """Subscriber registration failed."""


class EventDispatchError(
    EventBusError
):
    """Event dispatch failed."""


# =========================================================
# Metrics
# =========================================================

@dataclass(slots=True)
class EventBusMetrics:

    events_emitted: int = 0

    events_processed: int = 0

    events_failed: int = 0

    subscribers_total: int = 0

    dispatch_queue_size: int = 0

    active_workers: int = 0

    last_event_timestamp: float = 0.0


# =========================================================
# Internal Queue Event
# =========================================================

@dataclass(slots=True)
class QueuedEvent:

    event: TransportEvent

    queued_at: float = field(
        default_factory=time.time
    )


# =========================================================
# Event Bus
# =========================================================

class EventBus:
    """
    Async high-performance event bus.

    Features
    ------------------------------------------------
    - async pub/sub
    - wildcard listeners
    - fanout dispatch
    - background workers
    - metrics
    - non-blocking pipeline
    - thread-safe async runtime
    """

    WILDCARD = "*"

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        worker_count: int = 2,
        queue_maxsize: int = 10_000,
    ) -> None:

        if worker_count <= 0:
            raise ValueError(
                "worker_count must be > 0"
            )

        self._logger = logging.getLogger(
            self.__class__.__name__
        )

        # =============================================
        # event_type -> callbacks
        # =============================================

        self._subscribers: DefaultDict[
            str,
            Set[EventCallback],
        ] = defaultdict(set)

        # =============================================
        # Async queue
        # =============================================

        self._queue: asyncio.Queue[
            QueuedEvent
        ] = asyncio.Queue(
            maxsize=queue_maxsize
        )

        # =============================================
        # Worker runtime
        # =============================================

        self._worker_count = worker_count

        self._workers: List[
            asyncio.Task
        ] = []

        self._running = False

        # =============================================
        # Metrics
        # =============================================

        self._metrics = EventBusMetrics()

    # =====================================================
    # Lifecycle
    # =====================================================

    async def start(self) -> None:

        if self._running:
            return

        self._running = True

        for _ in range(
            self._worker_count
        ):

            task = asyncio.create_task(
                self._worker_loop()
            )

            self._workers.append(task)

        self._metrics.active_workers = (
            len(self._workers)
        )

    async def stop(self) -> None:

        self._running = False

        for worker in self._workers:
            worker.cancel()

        if self._workers:

            await asyncio.gather(
                *self._workers,
                return_exceptions=True,
            )

        self._workers.clear()

        self._metrics.active_workers = 0

    # =====================================================
    # Subscribe
    # =====================================================

    def subscribe(
        self,
        event_type: (
            str
            | TransportEventType
        ),
        callback: EventCallback,
    ) -> None:
        """
        Subscribe to event type.

        Supports wildcard:
            "*"
        """

        if not callable(callback):

            raise (
                EventSubscriptionError(
                    "callback must be callable"
                )
            )

        normalized = (
            self._normalize_event_type(
                event_type
            )
        )

        self._subscribers[
            normalized
        ].add(callback)

        self._recalculate_subscribers()

    def unsubscribe(
        self,
        event_type: (
            str
            | TransportEventType
        ),
        callback: EventCallback,
    ) -> None:

        normalized = (
            self._normalize_event_type(
                event_type
            )
        )

        callbacks = (
            self._subscribers.get(
                normalized
            )
        )

        if not callbacks:
            return

        callbacks.discard(callback)

        if not callbacks:
            self._subscribers.pop(
                normalized,
                None,
            )

        self._recalculate_subscribers()

    # =====================================================
    # Emit
    # =====================================================

    async def emit(
        self,
        event: TransportEvent,
    ) -> None:
        """
        Queue event for async dispatch.
        """

        if not isinstance(
            event,
            TransportEvent,
        ):
            raise EventBusError(
                "event must be TransportEvent"
            )

        queued_event = QueuedEvent(
            event=event
        )

        await self._queue.put(
            queued_event
        )

        self._metrics.events_emitted += 1

        self._metrics.dispatch_queue_size = (
            self._queue.qsize()
        )

        self._metrics.last_event_timestamp = (
            time.time()
        )

    # =====================================================
    # Worker Loop
    # =====================================================

    async def _worker_loop(
        self,
    ) -> None:

        while self._running:

            try:

                queued_event = (
                    await self._queue.get()
                )

                await self._dispatch(
                    queued_event.event
                )

                self._queue.task_done()

                self._metrics.events_processed += 1

                self._metrics.dispatch_queue_size = (
                    self._queue.qsize()
                )

            except asyncio.CancelledError:
                break

            except Exception as exc:

                self._metrics.events_failed += 1

                self._logger.exception(
                    "Event worker failed: %s",
                    exc,
                )

    # =====================================================
    # Dispatch
    # =====================================================

    async def _dispatch(
        self,
        event: TransportEvent,
    ) -> None:

        event_type = (
            self._normalize_event_type(
                event.event_type
            )
        )

        callbacks: Set[
            EventCallback
        ] = set()

        # =============================================
        # Exact listeners
        # =============================================

        callbacks.update(
            self._subscribers.get(
                event_type,
                set(),
            )
        )

        # =============================================
        # Wildcard listeners
        # =============================================

        callbacks.update(
            self._subscribers.get(
                self.WILDCARD,
                set(),
            )
        )

        if not callbacks:
            return

        # =============================================
        # Fanout dispatch
        # =============================================

        await asyncio.gather(
            *[
                self._safe_invoke(
                    callback,
                    event,
                )
                for callback
                in callbacks
            ],
            return_exceptions=True,
        )

    # =====================================================
    # Safe Callback Invoke
    # =====================================================

    async def _safe_invoke(
        self,
        callback: EventCallback,
        event: TransportEvent,
    ) -> None:

        try:

            result = callback(event)

            if inspect.isawaitable(
                result
            ):
                await result

        except Exception as exc:

            self._metrics.events_failed += 1

            self._logger.exception(
                "Event callback failed: %s",
                exc,
            )

    # =====================================================
    # Helpers
    # =====================================================

    @staticmethod
    def _normalize_event_type(
        event_type: (
            str
            | TransportEventType
        ),
    ) -> str:

        if isinstance(
            event_type,
            TransportEventType,
        ):
            return (
                event_type.value
            )

        return str(
            event_type
        ).strip().lower()

    def _recalculate_subscribers(
        self,
    ) -> None:

        total = sum(
            len(callbacks)
            for callbacks
            in self._subscribers.values()
        )

        self._metrics.subscribers_total = (
            total
        )

    # =====================================================
    # Utility APIs
    # =====================================================

    async def wait_until_idle(
        self,
    ) -> None:

        await self._queue.join()

    def clear_subscribers(
        self,
    ) -> None:

        self._subscribers.clear()

        self._recalculate_subscribers()

    def subscriber_count(
        self,
    ) -> int:

        return (
            self._metrics.subscribers_total
        )

    def queue_size(
        self,
    ) -> int:

        return self._queue.qsize()

    def metrics(
        self,
    ) -> Dict[str, Any]:

        return {
            "events_emitted":
                self._metrics.events_emitted,

            "events_processed":
                self._metrics.events_processed,

            "events_failed":
                self._metrics.events_failed,

            "subscribers_total":
                self._metrics.subscribers_total,

            "dispatch_queue_size":
                self._metrics.dispatch_queue_size,

            "active_workers":
                self._metrics.active_workers,

            "last_event_timestamp":
                self._metrics.last_event_timestamp,
        }

    # =====================================================
    # Convenience Emitters
    # =====================================================

    async def emit_simple(
        self,
        *,
        event_type: (
            str
            | TransportEventType
        ),

        peer_id: Optional[
            str
        ] = None,

        packet_id: Optional[
            str
        ] = None,

        metadata: Optional[
            dict
        ] = None,
    ) -> None:

        event = TransportEvent(
            event_id=str(uuid.uuid4()),

            event_type=(
                event_type
            ),

            peer_id=peer_id,

            packet_id=packet_id,

            metadata=(
                metadata or {}
            ),
        )

        await self.emit(event)

    # =====================================================
    # Context Manager
    # =====================================================

    async def __aenter__(
        self,
    ) -> "EventBus":

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

    "EventBus",

    "EventBusError",
    "EventSubscriptionError",
    "EventDispatchError",

    "EventBusMetrics",

    "QueuedEvent",
]
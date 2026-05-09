from __future__ import annotations

import heapq
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Final, List

from .base_replay_cache import BaseReplayCache, ReplayCacheError


# =========================================================
# Constants
# =========================================================

DEFAULT_MAX_CACHE_SIZE: Final[int] = 100_000
DEFAULT_CLEANUP_INTERVAL_SECONDS: Final[int] = 60


# =========================================================
# Exceptions
# =========================================================

class MemoryReplayCacheError(ReplayCacheError):
    """Memory replay cache error."""


class MemoryReplayCacheFullError(MemoryReplayCacheError):
    """Replay cache exceeded maximum capacity."""


class MemoryReplayKeyNotFoundError(MemoryReplayCacheError):
    """Replay key not found."""


# =========================================================
# Cache Record
# =========================================================

@dataclass(slots=True, frozen=True)
class MemoryReplayCacheRecord:
    """
    Replay cache entry.

    replay_key:
        sender_fp:message_id

    expires_at_unix:
        Unix UTC expiration timestamp.
    """

    replay_key: str

    created_at_unix: float
    expires_at_unix: float

    message_id: str
    sender_fingerprint: str | None = None


# =========================================================
# Replay Cache
# =========================================================

class MemoryReplayCache(
    BaseReplayCache
):
    def __init__(
        self,
        *,
        max_cache_size: int = DEFAULT_MAX_CACHE_SIZE,
        cleanup_interval_seconds: int = DEFAULT_CLEANUP_INTERVAL_SECONDS,
    ) -> None:

        if max_cache_size <= 0:
            raise ValueError(
                "max_cache_size must be > 0."
            )

        if cleanup_interval_seconds <= 0:
            raise ValueError(
                "cleanup_interval_seconds must be > 0."
            )

        self.max_cache_size = max_cache_size

        self.cleanup_interval_seconds = (
            cleanup_interval_seconds
        )

        # replay_key -> record
        self._records: Dict[
            str,
            MemoryReplayCacheRecord,
        ] = {}

        # (expires_at_unix, replay_key)
        self._expiry_heap: List[
            tuple[float, str]
        ] = []

        self._lock = threading.RLock()

        self._last_cleanup_monotonic = (
            time.monotonic()
        )

    # =====================================================
    # Time Helpers
    # =====================================================

    @staticmethod
    def utc_now_unix() -> float:
        """
        UTC unix timestamp.
        """
        return datetime.now(
            timezone.utc
        ).timestamp()

    def _should_cleanup(self) -> bool:
        elapsed = (
            time.monotonic()
            - self._last_cleanup_monotonic
        )

        return (
            elapsed >= self.cleanup_interval_seconds
        )

    def _mark_cleanup(self) -> None:
        self._last_cleanup_monotonic = (
            time.monotonic()
        )

    # =====================================================
    # Validation
    # =====================================================

    @staticmethod
    def _validate_replay_key(
        replay_key: str,
    ) -> str:
        if not isinstance(replay_key, str):
            raise MemoryReplayCacheError(
                "replay_key must be a string."
            )

        replay_key = replay_key.strip()

        if not replay_key:
            raise MemoryReplayCacheError(
                "replay_key cannot be empty."
            )

        return replay_key

    # =====================================================
    # Core Cache Operations
    # =====================================================

    def has(
        self,
        replay_key: str,
    ) -> bool:
        """
        O(1) replay lookup.
        """
        replay_key = self._validate_replay_key(
            replay_key
        )

        with self._lock:
            return replay_key in self._records

    def get(
        self,
        replay_key: str,
    ) -> MemoryReplayCacheRecord:
        """
        Get replay record.
        """
        replay_key = self._validate_replay_key(
            replay_key
        )

        with self._lock:

            record = self._records.get(
                replay_key
            )

            if record is None:
                raise MemoryReplayKeyNotFoundError(
                    f"Replay key not found: "
                    f"{replay_key}"
                )

            return record

    def put(
        self,
        record: MemoryReplayCacheRecord,
    ) -> None:
        """
        Insert replay record.

        Complexity:
            O(log n)
        """

        if not isinstance(
            record,
            MemoryReplayCacheRecord,
        ):
            raise MemoryReplayCacheError(
                "record must be MemoryReplayCacheRecord."
            )

        with self._lock:

            if self._should_cleanup():
                self.cleanup()

            # Existing replay key
            if (
                record.replay_key
                in self._records
            ):
                self._records[
                    record.replay_key
                ] = record

                heapq.heappush(
                    self._expiry_heap,
                    (
                        record.expires_at_unix,
                        record.replay_key,
                    ),
                )

                return

            # Hard limit
            if (
                len(self._records)
                >= self.max_cache_size
            ):
                self.cleanup()

            # Still full after cleanup
            if (
                len(self._records)
                >= self.max_cache_size
            ):
                self._evict_oldest()

            self._records[
                record.replay_key
            ] = record

            heapq.heappush(
                self._expiry_heap,
                (
                    record.expires_at_unix,
                    record.replay_key,
                ),
            )

    def remove(
        self,
        replay_key: str,
    ) -> None:
        """
        Remove replay key.

        O(1) dict delete.
        """
        replay_key = self._validate_replay_key(
            replay_key
        )

        with self._lock:
            self._records.pop(
                replay_key,
                None,
            )

    # =====================================================
    # Expiration Cleanup
    # =====================================================

    def cleanup(self) -> int:
        """
        Efficient heap-based expiration cleanup.

        Complexity:
            O(k log n)

        where:
            k = expired entries
        """

        now = self.utc_now_unix()

        removed = 0

        with self._lock:

            while self._expiry_heap:

                expires_at, replay_key = (
                    self._expiry_heap[0]
                )

                if expires_at > now:
                    break

                heapq.heappop(
                    self._expiry_heap
                )

                current_record = (
                    self._records.get(
                        replay_key
                    )
                )

                # stale heap entry
                if current_record is None:
                    continue

                # newer version exists
                if (
                    current_record.expires_at_unix
                    != expires_at
                ):
                    continue

                del self._records[replay_key]

                removed += 1

            self._mark_cleanup()

        return removed

    # =====================================================
    # Eviction
    # =====================================================

    def _evict_oldest(self) -> None:
        """
        Evict oldest-expiring record.

        Production fallback safety.
        """

        while self._expiry_heap:

            expires_at, replay_key = (
                heapq.heappop(
                    self._expiry_heap
                )
            )

            current_record = (
                self._records.get(
                    replay_key
                )
            )

            if current_record is None:
                continue

            if (
                current_record.expires_at_unix
                != expires_at
            ):
                continue

            del self._records[replay_key]

            return

        raise MemoryReplayCacheFullError(
            "Replay cache eviction failed."
        )

    # =====================================================
    # State Management
    # =====================================================

    def clear(self) -> None:
        """
        Clear entire replay cache.
        """
        with self._lock:
            self._records.clear()
            self._expiry_heap.clear()

    def size(self) -> int:
        """
        Current cache size.
        """
        with self._lock:
            return len(self._records)

    def is_empty(self) -> bool:
        """
        Cache empty check.
        """
        return self.size() == 0

    # =====================================================
    # Debug / Metrics
    # =====================================================

    def stats(self) -> dict:
        """
        Cache statistics.
        """
        with self._lock:
            return {
                "records": len(
                    self._records
                ),
                "heap_entries": len(
                    self._expiry_heap
                ),
                "max_cache_size": (
                    self.max_cache_size
                ),
                "cleanup_interval_seconds": (
                    self.cleanup_interval_seconds
                ),
            }

    def export_state(
        self,
    ) -> dict:
        """
        Debug export.

        Never expose in production APIs.
        """

        with self._lock:
            return {
                replay_key: {
                    "created_at_unix": (
                        record.created_at_unix
                    ),
                    "expires_at_unix": (
                        record.expires_at_unix
                    ),
                    "message_id": (
                        record.message_id
                    ),
                    "sender_fingerprint": (
                        record.sender_fingerprint
                    ),
                }
                for replay_key, record
                in self._records.items()
            }


__all__ = [
    "MemoryReplayCacheError",
    "MemoryReplayCacheFullError",
    "MemoryReplayKeyNotFoundError",
    "MemoryReplayCacheRecord",
    "MemoryReplayCache",
]
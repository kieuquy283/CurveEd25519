from __future__ import annotations

import heapq
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Final, List


# =========================================================
# Constants
# =========================================================

DEFAULT_NONCE_TTL_SECONDS: Final[int] = 300

DEFAULT_MAX_NONCES: Final[int] = 200_000

DEFAULT_CLEANUP_INTERVAL_SECONDS: Final[int] = 60


# =========================================================
# Exceptions
# =========================================================

class NonceRegistryError(Exception):
    """Base nonce registry exception."""


class NonceAlreadyUsedError(NonceRegistryError):
    """Nonce reuse detected."""


class NonceRegistryFullError(NonceRegistryError):
    """Nonce registry exceeded maximum capacity."""


class InvalidNonceKeyError(NonceRegistryError):
    """Invalid nonce key."""


# =========================================================
# Nonce Record
# =========================================================

@dataclass(slots=True, frozen=True)
class NonceRecord:
    """
    Immutable nonce registry entry.
    """

    nonce_key: str

    created_at_unix: float

    expires_at_unix: float

    domain: str | None = None

    metadata: dict | None = None


# =========================================================
# Base Registry
# =========================================================

class BaseNonceRegistry(ABC):

    @abstractmethod
    def exists(
        self,
        *,
        nonce_key: str,
    ) -> bool:
        pass

    @abstractmethod
    def register(
        self,
        *,
        record: NonceRecord,
    ) -> None:
        pass

    @abstractmethod
    def cleanup(self) -> int:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass

    @abstractmethod
    def size(self) -> int:
        pass


# =========================================================
# Memory Nonce Registry
# =========================================================

class MemoryNonceRegistry(
    BaseNonceRegistry
):
    """
    High-performance in-memory nonce registry.

    Security goals:
    - nonce uniqueness
    - replay-safe AEAD nonce tracking
    - thread-safe
    - bounded memory
    - efficient expiration cleanup

    Complexity:
    - exists: O(1)
    - register: O(log n)
    - cleanup: O(k log n)
    """

    def __init__(
        self,
        *,
        max_nonces: int = (
            DEFAULT_MAX_NONCES
        ),
        default_ttl_seconds: int = (
            DEFAULT_NONCE_TTL_SECONDS
        ),
        cleanup_interval_seconds: int = (
            DEFAULT_CLEANUP_INTERVAL_SECONDS
        ),
    ) -> None:

        if max_nonces <= 0:
            raise ValueError(
                "max_nonces must be > 0."
            )

        if default_ttl_seconds <= 0:
            raise ValueError(
                "default_ttl_seconds must be > 0."
            )

        if cleanup_interval_seconds <= 0:
            raise ValueError(
                "cleanup_interval_seconds must be > 0."
            )

        self.max_nonces = max_nonces

        self.default_ttl_seconds = (
            default_ttl_seconds
        )

        self.cleanup_interval_seconds = (
            cleanup_interval_seconds
        )

        # nonce_key -> NonceRecord
        self._records: Dict[
            str,
            NonceRecord,
        ] = {}

        # min-heap:
        # (expires_at_unix, nonce_key)
        self._expiry_heap: List[
            tuple[float, str]
        ] = []

        self._lock = threading.RLock()

        self._last_cleanup_monotonic = (
            time.monotonic()
        )

    # =====================================================
    # Time
    # =====================================================

    @staticmethod
    def utc_now_unix() -> float:
        return time.time()

    def _should_cleanup(self) -> bool:

        elapsed = (
            time.monotonic()
            - self._last_cleanup_monotonic
        )

        return (
            elapsed
            >= self.cleanup_interval_seconds
        )

    def _mark_cleanup(self) -> None:

        self._last_cleanup_monotonic = (
            time.monotonic()
        )

    # =====================================================
    # Validation
    # =====================================================

    @staticmethod
    def validate_nonce_key(
        nonce_key: str,
    ) -> str:

        if not isinstance(
            nonce_key,
            str,
        ):
            raise InvalidNonceKeyError(
                "nonce_key must be a string."
            )

        nonce_key = nonce_key.strip()

        if not nonce_key:
            raise InvalidNonceKeyError(
                "nonce_key cannot be empty."
            )

        return nonce_key

    # =====================================================
    # Core Operations
    # =====================================================

    def exists(
        self,
        *,
        nonce_key: str,
    ) -> bool:

        nonce_key = (
            self.validate_nonce_key(
                nonce_key
            )
        )

        with self._lock:

            record = self._records.get(
                nonce_key
            )

            if record is None:
                return False

            now = self.utc_now_unix()

            # lazy expiration
            if (
                record.expires_at_unix
                <= now
            ):
                del self._records[
                    nonce_key
                ]

                return False

            return True

    def register(
        self,
        *,
        record: NonceRecord,
    ) -> None:

        if not isinstance(
            record,
            NonceRecord,
        ):
            raise NonceRegistryError(
                "record must be NonceRecord."
            )

        nonce_key = (
            self.validate_nonce_key(
                record.nonce_key
            )
        )

        with self._lock:

            if self._should_cleanup():
                self.cleanup()

            # =================================================
            # Nonce reuse detection
            # =================================================

            existing = (
                self._records.get(
                    nonce_key
                )
            )

            if existing is not None:

                now = self.utc_now_unix()

                # existing nonce still valid
                if (
                    existing.expires_at_unix
                    > now
                ):
                    raise (
                        NonceAlreadyUsedError(
                            f"Nonce already used: "
                            f"{nonce_key}"
                        )
                    )

                # expired → overwrite
                del self._records[
                    nonce_key
                ]

            # =================================================
            # Capacity management
            # =================================================

            if (
                len(self._records)
                >= self.max_nonces
            ):
                self.cleanup()

            if (
                len(self._records)
                >= self.max_nonces
            ):
                self._evict_oldest()

            # =================================================
            # Store
            # =================================================

            self._records[
                nonce_key
            ] = record

            heapq.heappush(
                self._expiry_heap,
                (
                    record.expires_at_unix,
                    nonce_key,
                ),
            )

    # =====================================================
    # Cleanup
    # =====================================================

    def cleanup(self) -> int:

        now = self.utc_now_unix()

        removed = 0

        with self._lock:

            while self._expiry_heap:

                expires_at, nonce_key = (
                    self._expiry_heap[0]
                )

                if expires_at > now:
                    break

                heapq.heappop(
                    self._expiry_heap
                )

                current = (
                    self._records.get(
                        nonce_key
                    )
                )

                if current is None:
                    continue

                # stale heap entry
                if (
                    current.expires_at_unix
                    != expires_at
                ):
                    continue

                del self._records[
                    nonce_key
                ]

                removed += 1

            self._mark_cleanup()

        return removed

    # =====================================================
    # Eviction
    # =====================================================

    def _evict_oldest(self) -> None:
        """
        Evict oldest-expiring nonce.

        Production safety fallback.
        """

        while self._expiry_heap:

            expires_at, nonce_key = (
                heapq.heappop(
                    self._expiry_heap
                )
            )

            current = (
                self._records.get(
                    nonce_key
                )
            )

            if current is None:
                continue

            if (
                current.expires_at_unix
                != expires_at
            ):
                continue

            del self._records[
                nonce_key
            ]

            return

        raise NonceRegistryFullError(
            "Nonce eviction failed."
        )

    # =====================================================
    # State Management
    # =====================================================

    def clear(self) -> None:

        with self._lock:

            self._records.clear()

            self._expiry_heap.clear()

    def size(self) -> int:

        with self._lock:
            return len(self._records)

    def is_empty(self) -> bool:

        return self.size() == 0

    # =====================================================
    # Metrics / Debug
    # =====================================================

    def stats(self) -> dict:

        with self._lock:

            return {
                "records": len(
                    self._records
                ),

                "heap_entries": len(
                    self._expiry_heap
                ),

                "max_nonces": (
                    self.max_nonces
                ),

                "default_ttl_seconds": (
                    self.default_ttl_seconds
                ),

                "cleanup_interval_seconds": (
                    self.cleanup_interval_seconds
                ),
            }

    def export_state(self) -> dict:
        """
        Debug export.

        Never expose in production APIs.
        """

        with self._lock:

            return {
                nonce_key: {
                    "created_at_unix":
                        record.created_at_unix,

                    "expires_at_unix":
                        record.expires_at_unix,

                    "domain":
                        record.domain,

                    "metadata":
                        record.metadata,
                }
                for nonce_key, record
                in self._records.items()
            }


__all__ = [
    "NonceRegistryError",
    "NonceAlreadyUsedError",
    "NonceRegistryFullError",
    "InvalidNonceKeyError",

    "NonceRecord",

    "BaseNonceRegistry",

    "MemoryNonceRegistry",
]
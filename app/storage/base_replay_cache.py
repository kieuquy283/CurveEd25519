from __future__ import annotations

from abc import ABC, abstractmethod

from .replay_record import ReplayCacheRecord


class ReplayCacheError(Exception):
    """Base replay cache exception."""



class BaseReplayCache(ABC):
    """
    Abstract replay cache backend.

    Implementations:
    - MemoryReplayCache
    - SQLiteReplayCache
    - RedisReplayCache (future)
    """

    @abstractmethod
    def has(
        self,
        replay_key: str,
    ) -> bool:
        """
        Check replay existence.
        """
        raise NotImplementedError

    @abstractmethod
    def put(
        self,
        record: ReplayCacheRecord,
    ) -> None:
        """
        Store replay record.
        """
        raise NotImplementedError

    @abstractmethod
    def remove(
        self,
        replay_key: str,
    ) -> None:
        """
        Remove replay record.
        """
        raise NotImplementedError

    @abstractmethod
    def cleanup(self) -> int:
        """
        Cleanup expired entries.

        Returns:
            removed_count
        """
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """
        Clear entire cache.
        """
        raise NotImplementedError

    @abstractmethod
    def size(self) -> int:
        """
        Current cache size.
        """
        raise NotImplementedError

    def stats(self) -> dict:
        """
        Optional metrics.
        """
        return {}

    def export_state(self) -> dict:
        """
        Optional debug export.
        """
        return {}
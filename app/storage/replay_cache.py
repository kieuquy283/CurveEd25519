from __future__ import annotations

from abc import ABC, abstractmethod


class BaseReplayCache(ABC):

    @abstractmethod
    def has(
        self,
        replay_key: str,
    ) -> bool:
        pass

    @abstractmethod
    def put(
        self,
        record,
    ) -> None:
        pass

    @abstractmethod
    def cleanup(self) -> int:
        pass

    @abstractmethod
    def remove(
        self,
        replay_key: str,
    ) -> None:
        pass
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Final, Protocol

from ..core.envelope import JsonDict
from ..core.message_id import ensure_valid_message_id
from ..storage.base_replay_cache import (
    BaseReplayCache,
)
from ..storage.memory_replay_cache import (
    MemoryReplayCache,
)
from ..storage.replay_record import (
    ReplayCacheRecord,
)


# =========================================================
# Constants
# =========================================================

DEFAULT_MAX_FUTURE_SKEW_SECONDS: Final[int] = 30


# =========================================================
# Exceptions
# =========================================================

class ReplayProtectionError(Exception):
    """Base replay protection exception."""


class ReplayAttackDetected(ReplayProtectionError):
    """Replay packet detected."""


class PacketExpiredError(ReplayProtectionError):
    """Packet expired."""


class InvalidReplayMetadataError(ReplayProtectionError):
    """Invalid replay metadata."""


# =========================================================
# Time Helpers
# =========================================================

def utc_now() -> datetime:
    """
    UTC-aware current time.
    """
    return datetime.now(timezone.utc)


def parse_utc_iso8601(
    timestamp: str,
) -> datetime:
    """
    Parse ISO8601 UTC timestamp.

    Example:
        2026-05-07T12:30:00Z
    """

    if not isinstance(timestamp, str):
        raise InvalidReplayMetadataError(
            "created_at must be a string."
        )

    try:
        dt = datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )

    except Exception as exc:
        raise InvalidReplayMetadataError(
            "Invalid ISO8601 timestamp."
        ) from exc

    if dt.tzinfo is None:
        raise InvalidReplayMetadataError(
            "Timestamp must contain timezone."
        )

    return dt.astimezone(timezone.utc)


# =========================================================
# Replay Protection Service
# =========================================================

class ReplayProtectionService:
    """
    Production-grade replay protection service.

    Responsibilities:
    -----------------
    - validate replay metadata
    - expiration validation
    - future timestamp validation
    - replay detection logic

    Non-responsibilities:
    ---------------------
    - storage engine
    - persistence implementation
    - cache internals

    Storage backend is injected via BaseReplayCache.
    """

    def __init__(
        self,
        *,
        cache: BaseReplayCache | None = None,
        max_future_skew_seconds: int = (
            DEFAULT_MAX_FUTURE_SKEW_SECONDS
        ),
        clock: Callable[[], datetime] = utc_now,
    ) -> None:

        if max_future_skew_seconds < 0:
            raise ValueError(
                "max_future_skew_seconds must be >= 0."
            )

        self._cache = (
            cache
            if cache is not None
            else MemoryReplayCache()
        )

        self._clock = clock

        self.max_future_skew_seconds = (
            max_future_skew_seconds
        )

    # =====================================================
    # Internal Time
    # =====================================================

    def _now(self) -> datetime:
        return self._clock()

    # =====================================================
    # Replay Key
    # =====================================================

    @staticmethod
    def build_replay_key(
        *,
        sender_fingerprint: str | None,
        message_id: str,
    ) -> str:
        """
        Build sender-scoped replay key.

        Format:
            sender_fp:message_id
        """

        normalized_message_id = (
            ensure_valid_message_id(
                message_id
            )
        )

        sender_fp = (
            sender_fingerprint
            .strip()
            .lower()
            if sender_fingerprint
            else "unknown"
        )

        return (
            f"{sender_fp}:"
            f"{normalized_message_id}"
        )

    # =====================================================
    # Metadata Extraction
    # =====================================================

    def extract_replay_record(
        self,
        header: JsonDict,
    ) -> ReplayCacheRecord:
        """
        Extract replay metadata from header.
        """

        if not isinstance(header, dict):
            raise InvalidReplayMetadataError(
                "Header must be a dict."
            )

        required_fields = (
            "message_id",
            "created_at",
            "expires_in",
        )

        for field in required_fields:
            if field not in header:
                raise InvalidReplayMetadataError(
                    f"Header missing field: "
                    f"{field}"
                )

        raw_message_id = header[
            "message_id"
        ]

        created_at_raw = header[
            "created_at"
        ]

        expires_in = header[
            "expires_in"
        ]

        if not isinstance(
            expires_in,
            int,
        ):
            raise InvalidReplayMetadataError(
                "expires_in must be an integer."
            )

        if expires_in <= 0:
            raise InvalidReplayMetadataError(
                "expires_in must be > 0."
            )

        message_id = (
            ensure_valid_message_id(
                raw_message_id
            )
        )

        created_at = parse_utc_iso8601(
            created_at_raw
        )

        expires_at = (
            created_at
            + timedelta(
                seconds=expires_in
            )
        )

        sender_fp = None

        sender = header.get(
            "sender"
        )

        if isinstance(sender, dict):
            sender_fp = sender.get(
                "ed25519_fingerprint"
            )

        replay_key = (
            self.build_replay_key(
                sender_fingerprint=sender_fp,
                message_id=message_id,
            )
        )

        return ReplayCacheRecord(
            replay_key=replay_key,

            created_at_unix=(
                created_at.timestamp()
            ),

            expires_at_unix=(
                expires_at.timestamp()
            ),

            message_id=message_id,

            sender_fingerprint=sender_fp,
        )

    # =====================================================
    # Validation Helpers
    # =====================================================

    def is_expired(
        self,
        record: ReplayCacheRecord,
    ) -> bool:
        """
        Expiration validation.
        """

        now_unix = (
            self._now().timestamp()
        )

        return (
            now_unix
            > record.expires_at_unix
        )

    def is_from_future(
        self,
        record: ReplayCacheRecord,
    ) -> bool:
        """
        Future timestamp validation.
        """

        allowed_future_unix = (
            self._now().timestamp()
            + self.max_future_skew_seconds
        )

        return (
            record.created_at_unix
            > allowed_future_unix
        )

    # =====================================================
    # Main Validation Entry
    # =====================================================

    def validate_packet(
        self,
        header: JsonDict,
    ) -> ReplayCacheRecord:
        """
        Main replay validation flow.

        Flow:
            1. extract replay metadata
            2. future timestamp check
            3. expiration check
            4. replay detection
            5. register replay key
        """

        record = (
            self.extract_replay_record(
                header
            )
        )

        if self.is_from_future(
            record
        ):
            raise InvalidReplayMetadataError(
                "Packet timestamp too far in future."
            )

        if self.is_expired(
            record
        ):
            raise PacketExpiredError(
                "Packet expired."
            )

        self._cache.cleanup()

        if self._cache.has(
            record.replay_key
        ):
            raise ReplayAttackDetected(
                f"Replay detected: "
                f"{record.replay_key}"
            )

        self._cache.put(record)

        return record

    # =====================================================
    # Cache Management
    # =====================================================

    def clear(self) -> None:
        """
        Clear replay cache.
        """
        self._cache.clear()

    def cache_size(self) -> int:
        """
        Current replay cache size.
        """
        return self._cache.size()

    def cleanup(self) -> int:
        """
        Trigger cleanup manually.
        """
        return self._cache.cleanup()

    def export_cache_state(
        self,
    ) -> dict:
        """
        Debug helper.

        Never expose publicly in production APIs.
        """

        if hasattr(
            self._cache,
            "export_state",
        ):
            return (
                self._cache.export_state()
            )

        return {}

    def stats(self) -> dict:
        """
        Cache statistics.
        """

        if hasattr(
            self._cache,
            "stats",
        ):
            return self._cache.stats()

        return {}


__all__ = [
    "ReplayProtectionError",
    "ReplayAttackDetected",
    "PacketExpiredError",
    "InvalidReplayMetadataError",
    "ReplayProtectionService",
    "utc_now",
    "parse_utc_iso8601",
]
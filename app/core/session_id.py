from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final


# =========================================================
# Constants
# =========================================================

DEFAULT_SESSION_ID_PREFIX: Final[str] = "sess"

SESSION_ID_RANDOM_BYTES: Final[int] = 18

SESSION_ID_VERSION: Final[int] = 1

MIN_SESSION_ID_LENGTH: Final[int] = 16

MAX_SESSION_ID_LENGTH: Final[int] = 128


# =========================================================
# Exceptions
# =========================================================

class SessionIDError(Exception):
    """Base session ID exception."""


class InvalidSessionIDError(SessionIDError):
    """Session ID format invalid."""


# =========================================================
# Session ID Model
# =========================================================

@dataclass(slots=True, frozen=True)
class SessionIDMetadata:
    """
    Parsed session ID metadata.
    """

    raw: str

    prefix: str

    version: int

    timestamp_ms: int

    random_b64: str

    checksum: str


# =========================================================
# Session ID Service
# =========================================================

class SessionIDService:
    """
    Production-grade session ID generator.

    Design goals:
    - cryptographically secure
    - globally unique
    - sortable by time
    - URL-safe
    - compact
    - versioned
    - checksum protected

    Format:
    -------
    sess_v1_<timestamp_ms>_<random>_<checksum>

    Example:
    --------
    sess_v1_1746780405123_Bx2mD6rM1N2sYzQx6A_1f3a8c91
    """

    PREFIX = DEFAULT_SESSION_ID_PREFIX

    VERSION = SESSION_ID_VERSION

    RANDOM_BYTES = SESSION_ID_RANDOM_BYTES

    # =====================================================
    # Public API
    # =====================================================

    @classmethod
    def generate(
        cls,
        *,
        prefix: str | None = None,
    ) -> str:
        """
        Generate secure session ID.
        """

        prefix = (
            prefix.strip()
            if prefix
            else cls.PREFIX
        )

        cls._validate_prefix(prefix)

        timestamp_ms = cls._utc_timestamp_ms()

        random_bytes = secrets.token_bytes(
            cls.RANDOM_BYTES
        )

        random_b64 = cls._urlsafe_b64encode(
            random_bytes
        )

        checksum = cls._build_checksum(
            prefix=prefix,
            version=cls.VERSION,
            timestamp_ms=timestamp_ms,
            random_b64=random_b64,
        )

        return (
            f"{prefix}"
            f"_v{cls.VERSION}"
            f"_{timestamp_ms}"
            f"_{random_b64}"
            f"_{checksum}"
        )

    @classmethod
    def validate(
        cls,
        session_id: str,
    ) -> bool:
        """
        Validate session ID integrity.
        """

        try:
            parsed = cls.parse(session_id)

            expected_checksum = (
                cls._build_checksum(
                    prefix=parsed.prefix,
                    version=parsed.version,
                    timestamp_ms=parsed.timestamp_ms,
                    random_b64=parsed.random_b64,
                )
            )

            return secrets.compare_digest(
                expected_checksum,
                parsed.checksum,
            )

        except Exception:
            return False

    @classmethod
    def parse(
        cls,
        session_id: str,
    ) -> SessionIDMetadata:
        """
        Parse and validate structure.
        """

        cls._validate_session_id_type(
            session_id
        )

        parts = session_id.split("_")

        if len(parts) != 5:
            raise InvalidSessionIDError(
                "Invalid session ID format."
            )

        prefix = parts[0]

        version_part = parts[1]

        timestamp_part = parts[2]

        random_b64 = parts[3]

        checksum = parts[4]

        if not version_part.startswith("v"):
            raise InvalidSessionIDError(
                "Invalid version format."
            )

        try:
            version = int(version_part[1:])

        except ValueError as exc:
            raise InvalidSessionIDError(
                "Invalid session ID version."
            ) from exc

        try:
            timestamp_ms = int(timestamp_part)

        except ValueError as exc:
            raise InvalidSessionIDError(
                "Invalid timestamp."
            ) from exc

        cls._validate_prefix(prefix)

        cls._validate_random_component(
            random_b64
        )

        cls._validate_checksum(
            checksum
        )

        return SessionIDMetadata(
            raw=session_id,
            prefix=prefix,
            version=version,
            timestamp_ms=timestamp_ms,
            random_b64=random_b64,
            checksum=checksum,
        )

    @classmethod
    def extract_timestamp(
        cls,
        session_id: str,
    ) -> datetime:
        """
        Extract creation time from session ID.
        """

        parsed = cls.parse(session_id)

        return datetime.fromtimestamp(
            parsed.timestamp_ms / 1000,
            tz=timezone.utc,
        )

    @classmethod
    def is_expired(
        cls,
        session_id: str,
        *,
        max_age_seconds: int,
    ) -> bool:
        """
        Check session expiration.
        """

        if max_age_seconds <= 0:
            raise ValueError(
                "max_age_seconds must be > 0."
            )

        parsed = cls.parse(session_id)

        now_ms = cls._utc_timestamp_ms()

        age_ms = (
            now_ms
            - parsed.timestamp_ms
        )

        return (
            age_ms
            > max_age_seconds * 1000
        )

    # =====================================================
    # Validation
    # =====================================================

    @staticmethod
    def _validate_session_id_type(
        session_id: str,
    ) -> None:

        if not isinstance(session_id, str):
            raise InvalidSessionIDError(
                "Session ID must be a string."
            )

        session_id = session_id.strip()

        if not session_id:
            raise InvalidSessionIDError(
                "Session ID cannot be empty."
            )

        if (
            len(session_id)
            < MIN_SESSION_ID_LENGTH
        ):
            raise InvalidSessionIDError(
                "Session ID too short."
            )

        if (
            len(session_id)
            > MAX_SESSION_ID_LENGTH
        ):
            raise InvalidSessionIDError(
                "Session ID too long."
            )

    @staticmethod
    def _validate_prefix(
        prefix: str,
    ) -> None:

        if not prefix:
            raise InvalidSessionIDError(
                "Prefix cannot be empty."
            )

        if not prefix.replace("-", "").isalnum():
            raise InvalidSessionIDError(
                "Prefix must be alphanumeric."
            )

    @staticmethod
    def _validate_random_component(
        random_b64: str,
    ) -> None:

        if not random_b64:
            raise InvalidSessionIDError(
                "Random component missing."
            )

    @staticmethod
    def _validate_checksum(
        checksum: str,
    ) -> None:

        if len(checksum) != 8:
            raise InvalidSessionIDError(
                "Invalid checksum length."
            )

    # =====================================================
    # Internal Helpers
    # =====================================================

    @staticmethod
    def _utc_timestamp_ms() -> int:
        """
        UTC unix timestamp milliseconds.
        """

        return int(
            time.time() * 1000
        )

    @staticmethod
    def _urlsafe_b64encode(
        data: bytes,
    ) -> str:
        """
        URL-safe base64 without padding.
        """

        return (
            base64.urlsafe_b64encode(data)
            .decode("utf-8")
            .rstrip("=")
        )

    @staticmethod
    def _build_checksum(
        *,
        prefix: str,
        version: int,
        timestamp_ms: int,
        random_b64: str,
    ) -> str:
        """
        Lightweight integrity checksum.
        """

        raw = (
            f"{prefix}|"
            f"{version}|"
            f"{timestamp_ms}|"
            f"{random_b64}"
        ).encode("utf-8")

        digest = hashlib.sha256(
            raw
        ).hexdigest()

        return digest[:8]


# =========================================================
# Convenience Functions
# =========================================================

def generate_session_id() -> str:
    """
    Convenience helper.
    """

    return SessionIDService.generate()


def validate_session_id(
    session_id: str,
) -> bool:
    """
    Convenience helper.
    """

    return SessionIDService.validate(
        session_id
    )


def parse_session_id(
    session_id: str,
) -> SessionIDMetadata:
    """
    Convenience helper.
    """

    return SessionIDService.parse(
        session_id
    )


# =========================================================
# Public Exports
# =========================================================

__all__ = [
    "SessionIDError",
    "InvalidSessionIDError",
    "SessionIDMetadata",
    "SessionIDService",
    "generate_session_id",
    "validate_session_id",
    "parse_session_id",
]
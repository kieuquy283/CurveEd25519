from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final


# =========================================================
# Constants
# =========================================================

CHACHA20_NONCE_SIZE: Final[int] = 12

NONCE_DOMAIN_PAYLOAD: Final[str] = "payload"
NONCE_DOMAIN_WRAP: Final[str] = "wrap"
NONCE_DOMAIN_SESSION: Final[str] = "session"

ALLOWED_NONCE_DOMAINS: Final[set[str]] = {
    NONCE_DOMAIN_PAYLOAD,
    NONCE_DOMAIN_WRAP,
    NONCE_DOMAIN_SESSION,
}


# =========================================================
# Exceptions
# =========================================================

class NonceError(Exception):
    """Base nonce exception."""


class InvalidNonceError(NonceError):
    """Raised when nonce is invalid."""


class NonceDomainError(NonceError):
    """Raised when nonce domain is invalid."""


# =========================================================
# Nonce Metadata
# =========================================================

@dataclass(slots=True, frozen=True)
class NonceInfo:
    """
    Metadata for generated nonce.

    Attributes
    ----------
    domain:
        Nonce usage domain.

    nonce:
        Raw nonce bytes.

    nonce_b64:
        Base64 encoded nonce.

    created_at:
        ISO8601 UTC timestamp.
    """

    domain: str

    nonce: bytes

    nonce_b64: str

    created_at: str


# =========================================================
# Validation
# =========================================================

def validate_nonce_domain(domain: str) -> str:
    """
    Validate nonce domain.
    """

    if not isinstance(domain, str):
        raise NonceDomainError(
            "Nonce domain must be a string."
        )

    domain = domain.strip().lower()

    if not domain:
        raise NonceDomainError(
            "Nonce domain cannot be empty."
        )

    if domain not in ALLOWED_NONCE_DOMAINS:
        raise NonceDomainError(
            f"Unsupported nonce domain: {domain}"
        )

    return domain


def validate_nonce(
    nonce: bytes,
    *,
    expected_size: int = CHACHA20_NONCE_SIZE,
) -> bytes:
    """
    Validate nonce bytes.
    """

    if not isinstance(nonce, bytes):
        raise InvalidNonceError(
            "Nonce must be bytes."
        )

    if len(nonce) != expected_size:
        raise InvalidNonceError(
            f"Nonce must be "
            f"{expected_size} bytes."
        )

    return nonce


def validate_nonce_b64(
    nonce_b64: str,
    *,
    expected_size: int = CHACHA20_NONCE_SIZE,
) -> bytes:
    """
    Validate and decode base64 nonce.
    """

    if not isinstance(nonce_b64, str):
        raise InvalidNonceError(
            "Nonce base64 must be a string."
        )

    nonce_b64 = nonce_b64.strip()

    if not nonce_b64:
        raise InvalidNonceError(
            "Nonce base64 cannot be empty."
        )

    try:
        nonce = base64.b64decode(
            nonce_b64.encode("utf-8"),
            validate=True,
        )
    except Exception as exc:
        raise InvalidNonceError(
            "Invalid nonce base64."
        ) from exc

    return validate_nonce(
        nonce,
        expected_size=expected_size,
    )


# =========================================================
# Encoding Helpers
# =========================================================

def nonce_to_b64(
    nonce: bytes,
) -> str:
    """
    Encode nonce to base64.
    """

    validate_nonce(nonce)

    return base64.b64encode(
        nonce
    ).decode("utf-8")


def nonce_from_b64(
    nonce_b64: str,
) -> bytes:
    """
    Decode nonce from base64.
    """

    return validate_nonce_b64(
        nonce_b64
    )


# =========================================================
# Nonce Generation
# =========================================================

def generate_nonce(
    domain: str,
) -> bytes:
    """
    Generate cryptographically secure nonce.

    Parameters
    ----------
    domain:
        Logical nonce usage domain.

    Returns
    -------
    bytes
        Random nonce bytes.
    """

    validate_nonce_domain(domain)

    nonce = os.urandom(
        CHACHA20_NONCE_SIZE
    )

    return validate_nonce(
        nonce
    )


def generate_nonce_info(
    domain: str,
) -> NonceInfo:
    """
    Generate nonce + metadata.
    """

    domain = validate_nonce_domain(
        domain
    )

    nonce = generate_nonce(
        domain
    )

    created_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    return NonceInfo(
        domain=domain,
        nonce=nonce,
        nonce_b64=nonce_to_b64(
            nonce
        ),
        created_at=created_at,
    )


# =========================================================
# Utility Helpers
# =========================================================

def is_valid_nonce(
    nonce: bytes,
) -> bool:
    """
    Safe nonce validation check.
    """

    try:
        validate_nonce(nonce)
        return True
    except Exception:
        return False


def is_valid_nonce_b64(
    nonce_b64: str,
) -> bool:
    """
    Safe base64 nonce validation check.
    """

    try:
        validate_nonce_b64(
            nonce_b64
        )
        return True
    except Exception:
        return False


# =========================================================
# Exports
# =========================================================

__all__ = [
    # constants
    "CHACHA20_NONCE_SIZE",
    "NONCE_DOMAIN_PAYLOAD",
    "NONCE_DOMAIN_WRAP",
    "NONCE_DOMAIN_SESSION",
    "ALLOWED_NONCE_DOMAINS",

    # exceptions
    "NonceError",
    "InvalidNonceError",
    "NonceDomainError",

    # metadata
    "NonceInfo",

    # validation
    "validate_nonce_domain",
    "validate_nonce",
    "validate_nonce_b64",

    # encoding
    "nonce_to_b64",
    "nonce_from_b64",

    # generation
    "generate_nonce",
    "generate_nonce_info",

    # helpers
    "is_valid_nonce",
    "is_valid_nonce_b64",
]
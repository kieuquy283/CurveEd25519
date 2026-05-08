from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Final

from ..core.envelope import (
    b64e,
)

from ..core.nonce import (
    CHACHA20_NONCE_SIZE,
    NONCE_DOMAIN_PAYLOAD,
    NONCE_DOMAIN_WRAP,
    NONCE_DOMAIN_PROTOCOL,
    NONCE_DOMAIN_SIGNATURE,
    NONCE_SEPARATOR,
    generate_nonce,
    validate_nonce,
)

from ..storage.nonce_registry import (
    BaseNonceRegistry,
    MemoryNonceRegistry,
    NonceAlreadyUsedError,
    NonceRecord,
    NonceRegistryError,
)


# =========================================================
# Constants
# =========================================================

DEFAULT_NONCE_TTL_SECONDS: Final[int] = 300

MAX_GENERATION_RETRIES: Final[int] = 32


# =========================================================
# Exceptions
# =========================================================

class NonceServiceError(Exception):
    """Base nonce service exception."""


class NonceReuseDetectedError(
    NonceServiceError
):
    """Nonce reuse detected."""


class NonceGenerationError(
    NonceServiceError
):
    """Unable to generate unique nonce."""


class InvalidNonceDomainError(
    NonceServiceError
):
    """Invalid nonce domain."""


# =========================================================
# Nonce Result
# =========================================================

@dataclass(slots=True, frozen=True)
class ManagedNonce:
    """
    Generated + registered nonce.
    """

    nonce: bytes

    nonce_b64: str

    nonce_key: str

    domain: str

    created_at_unix: float

    expires_at_unix: float


# =========================================================
# Nonce Service
# =========================================================

class NonceService:
    """
    HIGH-LEVEL NONCE MANAGEMENT SYSTEM.

    Responsibilities:
    -----------------
    - secure nonce generation
    - nonce uniqueness enforcement
    - nonce reuse prevention
    - registry integration
    - domain separation
    - expiration policy
    - cleanup orchestration

    Security:
    ---------
    Prevents catastrophic AEAD nonce reuse.
    """

    # =====================================================
    # Allowed domains
    # =====================================================

    ALLOWED_DOMAINS = frozenset({
        NONCE_DOMAIN_PAYLOAD,
        NONCE_DOMAIN_WRAP,
        NONCE_DOMAIN_PROTOCOL,
        NONCE_DOMAIN_SIGNATURE,
    })

    # =====================================================
    # Init
    # =====================================================

    def __init__(
        self,
        *,
        registry: BaseNonceRegistry | None = None,
        default_ttl_seconds: int = (
            DEFAULT_NONCE_TTL_SECONDS
        ),
    ) -> None:

        if default_ttl_seconds <= 0:
            raise ValueError(
                "default_ttl_seconds must be > 0."
            )

        self.registry = (
            registry
            or MemoryNonceRegistry()
        )

        self.default_ttl_seconds = (
            default_ttl_seconds
        )

    # =====================================================
    # Main API
    # =====================================================

    def generate_unique_nonce(
        self,
        *,
        domain: str,
        ttl_seconds: int | None = None,
        metadata: dict | None = None,
    ) -> ManagedNonce:
        """
        Generate cryptographically secure
        UNIQUE nonce.

        Guarantees:
        -----------
        - cryptographic randomness
        - registry uniqueness
        - domain separation
        - expiration tracking
        """

        domain = self._validate_domain(
            domain
        )

        ttl_seconds = (
            ttl_seconds
            or self.default_ttl_seconds
        )

        now = time.time()

        expires_at = (
            now + ttl_seconds
        )

        # =================================================
        # Retry loop
        # =================================================

        for _ in range(
            MAX_GENERATION_RETRIES
        ):

            nonce = generate_nonce(
                domain
            )

            validate_nonce(
                nonce,
                expected_size=(
                    CHACHA20_NONCE_SIZE
                ),
            )

            nonce_b64 = b64e(nonce)

            nonce_key = (
                self.build_nonce_key(
                    domain=domain,
                    nonce_b64=nonce_b64,
                )
            )

            record = NonceRecord(
                nonce_key=nonce_key,

                created_at_unix=now,

                expires_at_unix=(
                    expires_at
                ),

                domain=domain,

                metadata=metadata,
            )

            try:

                self.registry.register(
                    record=record
                )

                return ManagedNonce(
                    nonce=nonce,

                    nonce_b64=nonce_b64,

                    nonce_key=nonce_key,

                    domain=domain,

                    created_at_unix=now,

                    expires_at_unix=(
                        expires_at
                    ),
                )

            except NonceAlreadyUsedError:
                continue

            except Exception as exc:
                raise (
                    NonceServiceError(
                        "Nonce registry failure."
                    )
                ) from exc

        raise NonceGenerationError(
            "Unable to generate unique nonce "
            "after maximum retries."
        )

    # =====================================================
    # Validation
    # =====================================================

    def ensure_nonce_unused(
        self,
        *,
        domain: str,
        nonce_b64: str,
    ) -> None:
        """
        Validate nonce has never been used.
        """

        domain = self._validate_domain(
            domain
        )

        nonce_key = (
            self.build_nonce_key(
                domain=domain,
                nonce_b64=nonce_b64,
            )
        )

        if self.registry.exists(
            nonce_key=nonce_key
        ):
            raise (
                NonceReuseDetectedError(
                    f"Nonce reuse detected: "
                    f"{nonce_key}"
                )
            )

    def register_external_nonce(
        self,
        *,
        domain: str,
        nonce_b64: str,
        ttl_seconds: int | None = None,
        metadata: dict | None = None,
    ) -> None:
        """
        Register externally supplied nonce.

        Useful for:
        - protocol receive path
        - remote nonce tracking
        - distributed systems
        """

        domain = self._validate_domain(
            domain
        )

        ttl_seconds = (
            ttl_seconds
            or self.default_ttl_seconds
        )

        now = time.time()

        expires_at = (
            now + ttl_seconds
        )

        nonce_key = (
            self.build_nonce_key(
                domain=domain,
                nonce_b64=nonce_b64,
            )
        )

        record = NonceRecord(
            nonce_key=nonce_key,

            created_at_unix=now,

            expires_at_unix=(
                expires_at
            ),

            domain=domain,

            metadata=metadata,
        )

        try:

            self.registry.register(
                record=record
            )

        except NonceAlreadyUsedError as exc:
            raise (
                NonceReuseDetectedError(
                    str(exc)
                )
            ) from exc

    # =====================================================
    # Cleanup
    # =====================================================

    def cleanup(self) -> int:
        """
        Cleanup expired nonce records.
        """

        return self.registry.cleanup()

    # =====================================================
    # Nonce Key
    # =====================================================

    @staticmethod
    def build_nonce_key(
        *,
        domain: str,
        nonce_b64: str,
    ) -> str:
        """
        Build globally unique nonce key.

        Format:
            domain:nonce_b64
        """

        return (
            f"{domain}"
            f"{NONCE_SEPARATOR}"
            f"{nonce_b64}"
        )

    # =====================================================
    # Validation Helpers
    # =====================================================

    def _validate_domain(
        self,
        domain: str,
    ) -> str:

        if not isinstance(
            domain,
            str,
        ):
            raise (
                InvalidNonceDomainError(
                    "domain must be string."
                )
            )

        domain = domain.strip()

        if (
            domain
            not in self.ALLOWED_DOMAINS
        ):
            raise (
                InvalidNonceDomainError(
                    f"Unsupported nonce domain: "
                    f"{domain}"
                )
            )

        return domain

    # =====================================================
    # Metrics
    # =====================================================

    def stats(self) -> dict:
        """
        Nonce system statistics.
        """

        registry_stats = {}

        if hasattr(
            self.registry,
            "stats",
        ):
            registry_stats = (
                self.registry.stats()
            )

        return {
            "default_ttl_seconds":
                self.default_ttl_seconds,

            "allowed_domains":
                sorted(
                    self.ALLOWED_DOMAINS
                ),

            "registry":
                registry_stats,
        }


__all__ = [
    "NonceServiceError",
    "NonceReuseDetectedError",
    "NonceGenerationError",
    "InvalidNonceDomainError",

    "ManagedNonce",

    "NonceService",
]
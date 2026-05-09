from __future__ import annotations

import hmac
import hashlib
from dataclasses import dataclass
from typing import Final

from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


# =========================================================
# Constants
# =========================================================

ROOT_KEY_LEN: Final[int] = 32
CHAIN_KEY_LEN: Final[int] = 32
MESSAGE_KEY_LEN: Final[int] = 32

DEFAULT_HASH = hashes.SHA256()

HKDF_INFO_ROOT: Final[bytes] = (
    b"secure-messenger/root-key-v1"
)

HKDF_INFO_CHAIN: Final[bytes] = (
    b"secure-messenger/chain-key-v1"
)

HKDF_INFO_MESSAGE: Final[bytes] = (
    b"secure-messenger/message-key-v1"
)

HKDF_INFO_RATCHET: Final[bytes] = (
    b"secure-messenger/ratchet-key-v1"
)


# =========================================================
# Exceptions
# =========================================================

class SessionKeyError(Exception):
    """Base session key exception."""


class InvalidKeyMaterialError(SessionKeyError):
    """Invalid key material."""


# =========================================================
# Data Models
# =========================================================

@dataclass(slots=True, frozen=True)
class RootKeyMaterial:
    """
    Initial session root material.
    """

    root_key: bytes
    send_chain_key: bytes
    recv_chain_key: bytes


@dataclass(slots=True, frozen=True)
class ChainKeyStep:
    """
    Chain ratchet step result.
    """

    next_chain_key: bytes
    message_key: bytes


@dataclass(slots=True, frozen=True)
class RatchetStep:
    """
    DH ratchet derivation result.
    """

    new_root_key: bytes
    new_chain_key: bytes


# =========================================================
# SessionKeyManager
# =========================================================

class SessionKeyManager:
    """
    Session key derivation engine.

    Responsibilities:
    - derive root keys
    - derive chain keys
    - derive message keys
    - perform symmetric ratchet
    - perform DH ratchet derivation

    Design:
    - immutable outputs
    - domain-separated HKDF contexts
    - HMAC-based symmetric ratchet
    - Signal-inspired architecture
    """

    # =====================================================
    # Public API
    # =====================================================

    @classmethod
    def derive_initial_keys(
        cls,
        *,
        shared_secret: bytes,
        session_salt: bytes,
        initiator: bool,
    ) -> RootKeyMaterial:
        """
        Derive initial session keys.

        Output:
        - root_key
        - send_chain_key
        - recv_chain_key
        """

        cls._validate_key_material(
            shared_secret,
            "shared_secret",
        )

        cls._validate_key_material(
            session_salt,
            "session_salt",
        )

        material = cls._hkdf_expand(
            input_key_material=shared_secret,
            salt=session_salt,
            info=HKDF_INFO_ROOT,
            length=(
                ROOT_KEY_LEN
                + CHAIN_KEY_LEN
                + CHAIN_KEY_LEN
            ),
        )

        root_key = material[:ROOT_KEY_LEN]

        chain_a = material[
            ROOT_KEY_LEN:
            ROOT_KEY_LEN + CHAIN_KEY_LEN
        ]

        chain_b = material[
            ROOT_KEY_LEN + CHAIN_KEY_LEN:
        ]

        # Deterministic direction assignment
        if initiator:
            send_chain_key = chain_a
            recv_chain_key = chain_b
        else:
            send_chain_key = chain_b
            recv_chain_key = chain_a

        return RootKeyMaterial(
            root_key=root_key,
            send_chain_key=send_chain_key,
            recv_chain_key=recv_chain_key,
        )

    # =====================================================
    # Symmetric Ratchet
    # =====================================================

    @classmethod
    def ratchet_chain_key(
        cls,
        *,
        chain_key: bytes,
    ) -> ChainKeyStep:
        """
        Symmetric-key ratchet.

        Derives:
        - next_chain_key
        - message_key

        Uses domain-separated HMAC derivation.
        """

        cls._validate_key_material(
            chain_key,
            "chain_key",
        )

        next_chain_key = cls._hmac_derive(
            key=chain_key,
            data=b"chain-step",
        )

        message_key = cls._hmac_derive(
            key=chain_key,
            data=b"message-step",
        )

        return ChainKeyStep(
            next_chain_key=next_chain_key,
            message_key=message_key,
        )

    # =====================================================
    # Message Key Expansion
    # =====================================================

    @classmethod
    def derive_message_key(
        cls,
        *,
        message_key_seed: bytes,
    ) -> bytes:
        """
        Expand message key seed into AEAD-ready key.
        """

        cls._validate_key_material(
            message_key_seed,
            "message_key_seed",
        )

        return cls._hkdf_expand(
            input_key_material=message_key_seed,
            salt=None,
            info=HKDF_INFO_MESSAGE,
            length=MESSAGE_KEY_LEN,
        )

    # =====================================================
    # DH Ratchet
    # =====================================================

    @classmethod
    def perform_dh_ratchet(
        cls,
        *,
        current_root_key: bytes,
        new_shared_secret: bytes,
    ) -> RatchetStep:
        """
        Perform DH ratchet step.

        Used when new X25519 exchange occurs.
        """

        cls._validate_key_material(
            current_root_key,
            "current_root_key",
        )

        cls._validate_key_material(
            new_shared_secret,
            "new_shared_secret",
        )

        material = cls._hkdf_expand(
            input_key_material=new_shared_secret,
            salt=current_root_key,
            info=HKDF_INFO_RATCHET,
            length=(
                ROOT_KEY_LEN
                + CHAIN_KEY_LEN
            ),
        )

        new_root_key = material[
            :ROOT_KEY_LEN
        ]

        new_chain_key = material[
            ROOT_KEY_LEN:
        ]

        return RatchetStep(
            new_root_key=new_root_key,
            new_chain_key=new_chain_key,
        )

    # =====================================================
    # Rekey
    # =====================================================

    @classmethod
    def rekey_root_key(
        cls,
        *,
        root_key: bytes,
        entropy: bytes,
    ) -> bytes:
        """
        Rekey root key using fresh entropy.
        """

        cls._validate_key_material(
            root_key,
            "root_key",
        )

        cls._validate_key_material(
            entropy,
            "entropy",
        )

        return cls._hkdf_expand(
            input_key_material=entropy,
            salt=root_key,
            info=b"secure-messenger/rekey-v1",
            length=ROOT_KEY_LEN,
        )

    # =====================================================
    # Internal HKDF
    # =====================================================

    @staticmethod
    def _hkdf_expand(
        *,
        input_key_material: bytes,
        salt: bytes | None,
        info: bytes,
        length: int,
    ) -> bytes:
        """
        HKDF-SHA256 expansion.
        """

        hkdf = HKDF(
            algorithm=DEFAULT_HASH,
            length=length,
            salt=salt,
            info=info,
        )

        return hkdf.derive(
            input_key_material
        )

    # =====================================================
    # Internal HMAC Ratchet
    # =====================================================

    @staticmethod
    def _hmac_derive(
        *,
        key: bytes,
        data: bytes,
    ) -> bytes:
        """
        Deterministic HMAC derivation.
        """

        return hmac.new(
            key,
            data,
            hashlib.sha256,
        ).digest()

    # =====================================================
    # Validation
    # =====================================================

    @staticmethod
    def _validate_key_material(
        data: bytes,
        field_name: str,
    ) -> None:

        if not isinstance(data, bytes):
            raise InvalidKeyMaterialError(
                f"{field_name} must be bytes."
            )

        if not data:
            raise InvalidKeyMaterialError(
                f"{field_name} cannot be empty."
            )

    # =====================================================
    # Secure Utilities
    # =====================================================

    @staticmethod
    def constant_time_compare(
        a: bytes,
        b: bytes,
    ) -> bool:
        """
        Constant-time comparison.
        """

        return hmac.compare_digest(
            a,
            b,
        )


__all__ = [
    "SessionKeyError",
    "InvalidKeyMaterialError",
    "RootKeyMaterial",
    "ChainKeyStep",
    "RatchetStep",
    "SessionKeyManager",
]
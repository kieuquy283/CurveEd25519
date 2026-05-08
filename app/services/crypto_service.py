from __future__ import annotations

import base64
from typing import Any, Dict, Tuple, Union

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import (
    ChaCha20Poly1305,
)
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ..core.envelope import (
    JsonDict,
    b64d,
    b64e,
    canonical_dumps,
    validate_envelope,
)

from ..core.x25519 import (
    derive_shared_secret_from_b64,
    generate_ephemeral_keypair,
    key_fingerprint_from_public_key_b64,
    
)



BytesOrStr = Union[bytes, str]


# =========================================================
# Exceptions
# =========================================================

class CryptoServiceError(Exception):
    """Base crypto service exception."""


class InvalidProfileError(CryptoServiceError):
    """Invalid or incomplete key/profile."""


class SignatureVerificationError(CryptoServiceError):
    """Signature verification failed."""


class DecryptionError(CryptoServiceError):
    """Authenticated decryption failed."""


# =========================================================
# CryptoService
# =========================================================

class CryptoService:
    """
    LOW-LEVEL CRYPTOGRAPHIC PRIMITIVES ONLY.

    Responsibilities:
    - Ed25519 sign / verify
    - X25519 shared secret
    - HKDF derivation
    - ChaCha20-Poly1305 encryption
    - payload key wrapping

    DOES NOT:
    - protocol orchestration
    - replay protection
    - envelope construction
    - message routing
    """

    # =====================================================
    # Suite constants
    # =====================================================

    WRAP_INFO = b"curve25519-demo/wrap-key-v1"


    PAYLOAD_KEY_LEN = 32
    CHACHA20_NONCE_LEN = 12

    HKDF_OUT_LEN = (
        PAYLOAD_KEY_LEN
        + CHACHA20_NONCE_LEN
    )

    # =====================================================
    # SIGN / VERIFY
    # =====================================================

    @classmethod
    def sign_bytes(
        cls,
        *,
        private_key_b64: str,
        data: bytes,
    ) -> bytes:
        """
        Low-level Ed25519 signing primitive.
        """

        private_key = (
            cls._load_ed25519_private_key_from_b64(
                private_key_b64
            )
        )

        return private_key.sign(data)

    @classmethod
    def verify_bytes(
        cls,
        *,
        public_key_b64: str,
        data: bytes,
        signature: bytes,
    ) -> bool:
        """
        Low-level Ed25519 verification primitive.
        """

        public_key = (
            cls._load_ed25519_public_key_from_b64(
                public_key_b64
            )
        )

        try:
            public_key.verify(
                signature,
                data,
            )
            return True

        except Exception:
            return False

    # =====================================================
    # ENCRYPT
    # =====================================================

    @classmethod
    def encrypt_payload(
        cls,
        *,
        receiver_x25519_public_b64: str,
        plaintext: bytes,
        aad: bytes = b"",
    ) -> JsonDict:
        """
        Hybrid encryption primitive.

        Output:
        - ciphertext
        - wrapped payload key
        - ephemeral public key
        - salts/nonces
        """

        # =================================================
        # Generate payload materials
        # =================================================

        payload_key = (
            cls.generate_random_bytes(
                cls.PAYLOAD_KEY_LEN
            )
        )

        payload_nonce = (
            cls.generate_random_bytes(
                cls.CHACHA20_NONCE_LEN
            )
        )

        # =================================================
        # Ephemeral X25519
        # =================================================

        eph = generate_ephemeral_keypair()

        # =================================================
        # Shared secret
        # =================================================

        shared_secret = (
            derive_shared_secret_from_b64(
                private_key_b64=(
                    eph.private_key_b64
                ),
                peer_public_key_b64=(
                    receiver_x25519_public_b64
                ),
            )
        )

        # =================================================
        # HKDF wrap material
        # =================================================

        salt_wrap = (
            cls.generate_random_bytes(16)
        )

        wrap_key, wrap_nonce = (
            cls.derive_wrap_material(
                shared_secret,
                salt_wrap,
            )
        )

        # =================================================
        # Encrypt payload
        # =================================================

        payload_cipher = (
            ChaCha20Poly1305(payload_key)
        )

        ciphertext = (
            payload_cipher.encrypt(
                payload_nonce,
                plaintext,
                aad,
            )
        )

        # =================================================
        # Wrap payload key
        # =================================================

        wrap_cipher = (
            ChaCha20Poly1305(wrap_key)
        )

        wrapped_key = (
            wrap_cipher.encrypt(
                wrap_nonce,
                payload_key,
                aad,
            )
        )

        return {
            "ciphertext_b64": b64e(
                ciphertext
            ),

            "wrapped_key_b64": b64e(
                wrapped_key
            ),

            "payload_nonce_b64": b64e(
                payload_nonce
            ),

            "salt_wrap_b64": b64e(
                salt_wrap
            ),

            "ephemeral_private_key_b64":
                eph.private_key_b64,

            "ephemeral_public_key_b64":
                eph.public_key_b64,

            "shared_secret_b64": b64e(
                shared_secret
            ),

            "payload_key_b64": b64e(
                payload_key
            ),

            "wrap_key_b64": b64e(
                wrap_key
            ),

            "wrap_nonce_b64": b64e(
                wrap_nonce
            ),
        }

    # =====================================================
    # DECRYPT
    # =====================================================

    @classmethod
    def decrypt_payload(
        cls,
        *,
        receiver_x25519_private_b64: str,
        envelope: JsonDict,
    ) -> bytes:
        """
        Hybrid decryption primitive.
        """

        validate_envelope(envelope)

        header = envelope["header"]

        crypto = header["crypto"]

        eph_public_b64 = (
            crypto[
                "ephemeral_x25519_public_key"
            ]
        )

        salt_wrap = b64d(
            crypto["salt_wrap"]
        )

        payload_nonce = b64d(
            crypto["payload_nonce"]
        )

        wrapped_key = b64d(
            envelope["wrapped_key"]
        )

        ciphertext = b64d(
            envelope["ciphertext"]
        )

        # =================================================
        # Shared secret
        # =================================================

        shared_secret = (
            derive_shared_secret_from_b64(
                private_key_b64=(
                    receiver_x25519_private_b64
                ),
                peer_public_key_b64=(
                    eph_public_b64
                ),
            )
        )

        # =================================================
        # HKDF wrap material
        # =================================================

        wrap_key, wrap_nonce = (
            cls.derive_wrap_material(
                shared_secret,
                salt_wrap,
            )
        )

        aad = canonical_dumps(header)

        # =================================================
        # Unwrap payload key
        # =================================================

        try:

            wrap_cipher = (
                ChaCha20Poly1305(wrap_key)
            )

            payload_key = (
                wrap_cipher.decrypt(
                    wrap_nonce,
                    wrapped_key,
                    aad,
                )
            )

            # =============================================
            # Decrypt payload
            # =============================================

            payload_cipher = (
                ChaCha20Poly1305(payload_key)
            )

            plaintext = (
                payload_cipher.decrypt(
                    payload_nonce,
                    ciphertext,
                    aad,
                )
            )

            return plaintext

        except Exception as exc:
            raise DecryptionError(
                "Authenticated decryption failed."
            ) from exc

    # =====================================================
    # HKDF
    # =====================================================

    @classmethod
    def derive_wrap_material(
        cls,
        shared_secret: bytes,
        salt_wrap: bytes,
    ) -> Tuple[bytes, bytes]:
        """
        Derive:
        - wrap_key
        - wrap_nonce
        """

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=cls.HKDF_OUT_LEN,
            salt=salt_wrap,
            info=cls.WRAP_INFO,
        )

        material = hkdf.derive(
            shared_secret
        )

        wrap_key = material[
            : cls.PAYLOAD_KEY_LEN
        ]

        wrap_nonce = material[
            cls.PAYLOAD_KEY_LEN :
            cls.PAYLOAD_KEY_LEN
            + cls.CHACHA20_NONCE_LEN
        ]

        return wrap_key, wrap_nonce

    # =====================================================
    # KEY LOADERS
    # =====================================================

    @staticmethod
    def _load_ed25519_private_key_from_b64(
        private_key_b64: str,
    ) -> Ed25519PrivateKey:

        raw = b64d(private_key_b64)

        if len(raw) != 32:
            raise InvalidProfileError(
                "Ed25519 private key must be 32 bytes."
            )

        return (
            Ed25519PrivateKey
            .from_private_bytes(raw)
        )

    @staticmethod
    def _load_ed25519_public_key_from_b64(
        public_key_b64: str,
    ) -> Ed25519PublicKey:

        raw = b64d(public_key_b64)

        if len(raw) != 32:
            raise InvalidProfileError(
                "Ed25519 public key must be 32 bytes."
            )

        return (
            Ed25519PublicKey
            .from_public_bytes(raw)
        )

    # =====================================================
    # UTILITIES
    # =====================================================

    @staticmethod
    def generate_random_bytes(
        length: int,
    ) -> bytes:

        import os

        return os.urandom(length)

    @staticmethod
    def sha256_hex(
        data: bytes,
    ) -> str:

        import hashlib

        return hashlib.sha256(
            data
        ).hexdigest()

    @staticmethod
    def fingerprint_public_key(
        public_key_b64: str,
    ) -> str:

        try:
            return (
                key_fingerprint_from_public_key_b64(
                    public_key_b64
                )
            )

        except Exception:
            return "invalid"

    @staticmethod
    def ensure_bytes(
        data: BytesOrStr,
    ) -> bytes:

        if isinstance(data, bytes):
            return data

        if isinstance(data, str):
            return data.encode("utf-8")

        raise TypeError(
            "Expected bytes or str."
        )
        
        # -----------------------
    # Compatibility helpers
    # -----------------------

    @classmethod
    def _b64decode(cls, value: str) -> bytes:
        return b64d(value)

    @classmethod
    def _safe_fingerprint(cls, public_key_b64: str) -> str:
        try:
            return cls.fingerprint_public_key(public_key_b64)
        except Exception:
            return "invalid"

    @classmethod
    def _get_ed25519_private_key_b64(cls, profile_or_b64: Union[JsonDict, str]) -> str:
        if isinstance(profile_or_b64, str):
            return profile_or_b64
        if isinstance(profile_or_b64, dict):
            ed = profile_or_b64.get("ed25519")
            if isinstance(ed, dict) and ed.get("private_key"):
                return ed["private_key"]
            # legacy keys
            if profile_or_b64.get("private_key"):
                return profile_or_b64["private_key"]
        raise InvalidProfileError("Missing ed25519 private key in profile/contact.")

    @classmethod
    def _get_ed25519_public_key_b64(cls, obj: Union[JsonDict, str]) -> str:
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            ed = obj.get("ed25519")
            if isinstance(ed, dict) and ed.get("public_key"):
                return ed["public_key"]
            if obj.get("ed25519_public_key"):
                return obj["ed25519_public_key"]
        raise InvalidProfileError("Missing ed25519 public key in profile/contact.")

    @classmethod
    def _get_x25519_public_key_b64(cls, obj: Union[JsonDict, str]) -> str:
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            x = obj.get("x25519")
            if isinstance(x, dict) and x.get("public_key"):
                return x["public_key"]
            if obj.get("x25519_public_key"):
                return obj["x25519_public_key"]
        raise InvalidProfileError("Missing x25519 public key in profile/contact.")

    @classmethod
    def _get_x25519_private_key_b64(cls, profile: Union[JsonDict, str]) -> str:
        if isinstance(profile, str):
            return profile
        if isinstance(profile, dict):
            x = profile.get("x25519")
            if isinstance(x, dict) and x.get("private_key"):
                return x["private_key"]
            if profile.get("x25519_private_key"):
                return profile["x25519_private_key"]
        raise InvalidProfileError("Missing x25519 private key in profile.")
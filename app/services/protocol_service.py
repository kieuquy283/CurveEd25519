from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..core.envelope import (
    JsonDict,
    EnvelopeError,
    b64e,
    b64d,
    canonical_dumps,
    validate_envelope,
    build_header,
    build_unsigned_envelope,
    build_signed_envelope,
    build_signing_bytes,
)

from ..core.message_id import generate_message_id

from .crypto_service import (
    CryptoService,
    CryptoServiceError,
    SignatureVerificationError,
)

from .replay_service import (
    ReplayProtectionService,
    ReplayAttackDetected,
    PacketExpiredError,
    InvalidReplayMetadataError,
)


class ProtocolServiceError(Exception):
    """Base protocol service exception."""


class ProtocolValidationError(ProtocolServiceError):
    """Envelope validation failed."""


class ProtocolReplayError(ProtocolServiceError):
    """Replay protection failed."""


class ProtocolSignatureError(ProtocolServiceError):
    """Signature verification failed."""


class ProtocolDecryptError(ProtocolServiceError):
    """Payload decryption failed."""


class ProtocolService:
    """
    Secure messaging protocol orchestration layer.

    Responsibilities:
    - build protocol metadata
    - envelope orchestration
    - signature verification
    - replay protection
    - crypto flow coordination

    DOES NOT:
    - implement low-level crypto primitives
    - implement replay cache
    - implement serialization internals
    """

    VERSION = 1

    SUITE = "X25519+HKDF-SHA256+ChaCha20-Poly1305+Ed25519"

    DEFAULT_EXPIRES_IN = 300

    from storage.sqlite_replay_cache import (
        SQLiteReplayCache,
    )

    _replay_service = ReplayProtectionService(
        cache=SQLiteReplayCache()
    )

    # =========================================================
    # SEND FLOW
    # =========================================================

    @classmethod
    def send_message(
        cls,
        *,
        sender_profile: JsonDict,
        receiver_contact: JsonDict,
        plaintext: str | bytes,
        expires_in: int = DEFAULT_EXPIRES_IN,
        include_debug: bool = False,
    ) -> JsonDict:
        """
        Full secure message send flow.

        Flow:
            build metadata
            -> encrypt payload
            -> build envelope
            -> sign envelope

        Returns:
            {
                "envelope": {...},
                "debug": {...} optional
            }
        """

        plaintext_bytes = cls._to_bytes(plaintext)

        sender_name = cls._get_name(sender_profile)
        receiver_name = cls._get_name(receiver_contact)

        sender_ed25519_private_b64 = (
            CryptoService._get_ed25519_private_key_b64(sender_profile)
        )

        sender_ed25519_public_b64 = (
            CryptoService._get_ed25519_public_key_b64(sender_profile)
        )

        receiver_x25519_public_b64 = (
            CryptoService._get_x25519_public_key_b64(receiver_contact)
        )

        # =====================================================
        # Protocol metadata
        # =====================================================

        message_id = generate_message_id()

        created_at = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

        # =====================================================
        # Encrypt payload
        # =====================================================

        crypto_result = CryptoService.encrypt_payload(
            receiver_x25519_public_b64=receiver_x25519_public_b64,
            plaintext=plaintext_bytes,
        )

        # =====================================================
        # Build authenticated header
        # =====================================================

        header = build_header(
            version=cls.VERSION,
            suite=cls.SUITE,

            message_id=message_id,

            created_at=created_at,
            expires_in=expires_in,

            sender_name=sender_name,
            sender_sig_public_b64=sender_ed25519_public_b64,
            sender_sig_fingerprint=CryptoService._safe_fingerprint(
                sender_ed25519_public_b64
            ),

            recipient_name=receiver_name,
            recipient_x25519_fingerprint=CryptoService._safe_fingerprint(
                receiver_x25519_public_b64
            ),

            ephemeral_x25519_public_b64=crypto_result[
                "ephemeral_public_key_b64"
            ],

            ephemeral_x25519_fingerprint=CryptoService._safe_fingerprint(
                crypto_result["ephemeral_public_key_b64"]
            ),

            salt_wrap_b64=crypto_result["salt_wrap_b64"],

            payload_nonce_b64=crypto_result["payload_nonce_b64"],
        )

        header_bytes = canonical_dumps(header)

        # =====================================================
        # Re-encrypt with authenticated AAD
        # =====================================================

        crypto_result = CryptoService.encrypt_payload(
            receiver_x25519_public_b64=receiver_x25519_public_b64,
            plaintext=plaintext_bytes,
            forced_payload_nonce=b64d(
                crypto_result["payload_nonce_b64"]
            ),
            forced_salt_wrap=b64d(
                crypto_result["salt_wrap_b64"]
            ),
            forced_ephemeral_private_key_b64=crypto_result[
                "ephemeral_private_key_b64"
            ],
            aad=header_bytes,
        )

        # =====================================================
        # Build unsigned envelope
        # =====================================================

        unsigned_envelope = build_unsigned_envelope(
            header=header,
            wrapped_key=b64d(
                crypto_result["wrapped_key_b64"]
            ),
            ciphertext=b64d(
                crypto_result["ciphertext_b64"]
            ),
        )

        # =====================================================
        # Sign envelope
        # =====================================================

        signing_bytes = build_signing_bytes(
            header=header,
            wrapped_key=b64d(
                unsigned_envelope["wrapped_key"]
            ),
            ciphertext=b64d(
                unsigned_envelope["ciphertext"]
            ),
        )

        signature = CryptoService.sign_bytes(
            private_key_b64=sender_ed25519_private_b64,
            data=signing_bytes,
        )

        envelope = build_signed_envelope(
            header=header,
            wrapped_key=b64d(
                unsigned_envelope["wrapped_key"]
            ),
            ciphertext=b64d(
                unsigned_envelope["ciphertext"]
            ),
            signature=signature,
        )

        result: JsonDict = {
            "envelope": envelope,
        }

        if include_debug:
            result["debug"] = {
                **crypto_result,
                "message_id": message_id,
                "created_at": created_at,
                "expires_in": expires_in,
            }

        return result

    # =========================================================
    # RECEIVE FLOW
    # =========================================================

    @classmethod
    def receive_message(
        cls,
        *,
        receiver_profile: JsonDict,
        envelope: JsonDict,
        sender_contact: Optional[JsonDict] = None,
        verify_signature: bool = True,
        enforce_replay_protection: bool = True,
        include_debug: bool = False,
    ) -> JsonDict:
        """
        Full secure receive flow.

        Flow:
            validate envelope
            -> verify signature
            -> replay protection
            -> decrypt payload
        """

        # =====================================================
        # Validate envelope structure
        # =====================================================

        try:
            validate_envelope(envelope)

        except EnvelopeError as exc:
            raise ProtocolValidationError(
                str(exc)
            ) from exc

        header = envelope["header"]

        # =====================================================
        # Extract sender public key
        # =====================================================

        sender_pub_from_envelope = (
            header["sender"]["ed25519_public_key"]
        )

        # =====================================================
        # Optional sender identity pinning
        # =====================================================

        if sender_contact is not None:

            sender_pub_from_contact = (
                CryptoService._get_ed25519_public_key_b64(
                    sender_contact
                )
            )

            if sender_pub_from_contact != sender_pub_from_envelope:
                raise ProtocolSignatureError(
                    "Sender public key mismatch."
                )

        # =====================================================
        # Verify signature
        # =====================================================

        verified = False

        if verify_signature:

            signing_bytes = build_signing_bytes(
                header=header,
                wrapped_key=b64d(
                    envelope["wrapped_key"]
                ),
                ciphertext=b64d(
                    envelope["ciphertext"]
                ),
            )

            verified = CryptoService.verify_bytes(
                public_key_b64=sender_pub_from_envelope,
                data=signing_bytes,
                signature=CryptoService._b64decode(
                    envelope["signature"]["value"]
                ),
            )

            if not verified:
                raise ProtocolSignatureError(
                    "Envelope signature invalid."
                )

        # =====================================================
        # IMPORTANT SECURITY INVARIANT
        #
        # Replay validation MUST happen:
        #   AFTER signature verification
        #   BEFORE decryption
        #
        # Otherwise attacker could forge replay metadata.
        # =====================================================

        if enforce_replay_protection:

            try:
                cls._replay_service.validate_packet(
                    header
                )

            except (
                ReplayAttackDetected,
                PacketExpiredError,
                InvalidReplayMetadataError,
            ) as exc:
                raise ProtocolReplayError(
                    str(exc)
                ) from exc

        # =====================================================
        # Decrypt payload
        # =====================================================

        try:

            plaintext_bytes = CryptoService.decrypt_payload(
                receiver_x25519_private_b64=(
                    CryptoService._get_x25519_private_key_b64(
                        receiver_profile
                    )
                ),
                envelope=envelope,
            )

        except CryptoServiceError as exc:
            raise ProtocolDecryptError(
                str(exc)
            ) from exc

        result: JsonDict = {
            "verified": verified,
        }

        try:
            result["plaintext"] = (
                plaintext_bytes.decode("utf-8")
            )

        except UnicodeDecodeError:
            result["plaintext_bytes_b64"] = (
                b64e(plaintext_bytes)
            )

        if include_debug:

            result["debug"] = {
                "message_id": header["message_id"],
                "sender": header["sender"]["name"],
                "receiver": header["receiver"]["name"],
                "created_at": header.get("created_at"),
                "expires_in": header.get("expires_in"),
            }

        return result

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _to_bytes(data: str | bytes) -> bytes:

        if isinstance(data, bytes):
            return data

        if isinstance(data, str):
            return data.encode("utf-8")

        raise TypeError(
            "Expected str or bytes."
        )

    @staticmethod
    def _get_name(data: JsonDict) -> str:

        return str(
            data.get("name")
            or data.get("profile_name")
            or data.get("contact_name")
            or "unknown"
        )
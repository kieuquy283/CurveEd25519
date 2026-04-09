from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, Union

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.x25519 import (
    derive_shared_secret_from_b64,
    generate_ephemeral_keypair,
    key_fingerprint_from_public_key_b64,
    load_public_key_from_b64,
    load_private_key_from_b64,
)


JsonDict = Dict[str, Any]
BytesOrStr = Union[bytes, str]


class CryptoServiceError(Exception):
    """Base exception for crypto service."""


class InvalidProfileError(CryptoServiceError):
    """Raised when a profile/contact structure is invalid or incomplete."""


class SignatureVerificationError(CryptoServiceError):
    """Raised when signature verification fails."""


class EnvelopeError(CryptoServiceError):
    """Raised when envelope format is invalid."""


class CryptoService:
    """
    Service layer cho app mật mã.

    Chức năng chính:
    - sign_message
    - verify_message
    - encrypt_message
    - decrypt_message

    Profile/contact đầu vào được kỳ vọng là dict.
    Hỗ trợ linh hoạt các dạng key phổ biến:
      {
        "name": "alice",
        "ed25519": {"private_key": "...", "public_key": "..."},
        "x25519":  {"private_key": "...", "public_key": "..."}
      }

    hoặc các biến thể flat:
      {
        "name": "alice",
        "ed25519_private_key": "...",
        "ed25519_public_key": "...",
        "x25519_private_key": "...",
        "x25519_public_key": "..."
      }
    """

    VERSION = 1
    SUITE = "X25519+HKDF-SHA256+ChaCha20-Poly1305+Ed25519"

    WRAP_INFO = b"curve25519-demo/wrap-key-v1"
    PAYLOAD_INFO = b"curve25519-demo/payload-v1"

    PAYLOAD_KEY_LEN = 32
    CHACHA20_NONCE_LEN = 12
    HKDF_OUT_LEN = PAYLOAD_KEY_LEN + CHACHA20_NONCE_LEN

    # =========================
    # Public API
    # =========================

    @classmethod
    def sign_message(cls, signer_profile: JsonDict, message: BytesOrStr) -> JsonDict:
        """
        Ký message bằng private key Ed25519 của signer.

        Returns:
            {
              "signer": "alice",
              "message_hash_sha256": "...hex...",
              "signature": "...base64...",
              "public_key": "...base64..."
            }
        """
        message_bytes = cls._to_bytes(message)

        signer_name = cls._get_name(signer_profile)
        private_key_b64 = cls._get_ed25519_private_key_b64(signer_profile)
        public_key_b64 = cls._get_ed25519_public_key_b64(signer_profile)

        private_key = cls._load_ed25519_private_key_from_b64(private_key_b64)
        signature = private_key.sign(message_bytes)

        return {
            "signer": signer_name,
            "message_hash_sha256": hashlib.sha256(message_bytes).hexdigest(),
            "signature": cls._b64encode(signature),
            "public_key": public_key_b64,
        }

    @classmethod
    def verify_message(
        cls,
        signer_contact: JsonDict,
        message: BytesOrStr,
        signature_b64: str,
    ) -> bool:
        """
        Verify chữ ký Ed25519.
        """
        message_bytes = cls._to_bytes(message)
        public_key_b64 = cls._get_ed25519_public_key_b64(signer_contact)
        public_key = cls._load_ed25519_public_key_from_b64(public_key_b64)
        signature = cls._b64decode(signature_b64)

        try:
            public_key.verify(signature, message_bytes)
            return True
        except Exception:
            return False

    @classmethod
    def encrypt_message(
        cls,
        sender_profile: JsonDict,
        receiver_contact: JsonDict,
        plaintext: BytesOrStr,
        include_debug: bool = True,
    ) -> JsonDict:
        """
        Hybrid encrypt + sign.

        Pipeline:
        - Generate payload_key + payload_nonce
        - Encrypt payload bằng ChaCha20-Poly1305
        - Generate ephemeral X25519 sender key
        - Derive shared secret với receiver public X25519
        - HKDF(shared_secret) -> wrap_key + wrap_nonce
        - Encrypt payload_key bằng wrap_key
        - Build envelope
        - Sign unsigned envelope bằng sender Ed25519 private key

        Returns:
            {
              "envelope": {...},
              "debug": {...}   # nếu include_debug=True
            }
        """
        plaintext_bytes = cls._to_bytes(plaintext)

        sender_name = cls._get_name(sender_profile)
        receiver_name = cls._get_name(receiver_contact)

        sender_ed25519_private_b64 = cls._get_ed25519_private_key_b64(sender_profile)
        sender_ed25519_public_b64 = cls._get_ed25519_public_key_b64(sender_profile)
        receiver_x25519_public_b64 = cls._get_x25519_public_key_b64(receiver_contact)

        # 1) Sinh payload key / nonce
        payload_key = os.urandom(cls.PAYLOAD_KEY_LEN)
        payload_nonce = os.urandom(cls.CHACHA20_NONCE_LEN)

        # 2) Sinh ephemeral X25519 keypair
        eph = generate_ephemeral_keypair()

        # 3) Derive shared secret
        shared_secret = derive_shared_secret_from_b64(
            private_key_b64=eph.private_key_b64,
            peer_public_key_b64=receiver_x25519_public_b64,
        )

        # 4) HKDF -> wrap_key + wrap_nonce
        salt_wrap = os.urandom(16)
        wrap_key, wrap_nonce = cls._derive_wrap_material(shared_secret, salt_wrap)

        # 5) Build header trước để dùng làm AAD
        msg_id = cls._b64encode(os.urandom(16))
        created_at = datetime.now(timezone.utc).isoformat()

        header = {
            "version": cls.VERSION,
            "suite": cls.SUITE,
            "message_id": msg_id,
            "created_at": created_at,
            "sender": {
                "name": sender_name,
                "ed25519_public_key": sender_ed25519_public_b64,
                "ed25519_fingerprint": cls._safe_fingerprint(sender_ed25519_public_b64),
            },
            "receiver": {
                "name": receiver_name,
                "x25519_fingerprint": cls._safe_fingerprint(receiver_x25519_public_b64),
            },
            "crypto": {
                "ephemeral_x25519_public_key": eph.public_key_b64,
                "ephemeral_x25519_fingerprint": cls._safe_fingerprint(eph.public_key_b64),
                "salt_wrap": cls._b64encode(salt_wrap),
                "payload_nonce": cls._b64encode(payload_nonce),
            },
        }

        header_bytes = cls._canonical_json_bytes(header)

        # 6) Encrypt payload
        payload_cipher = ChaCha20Poly1305(payload_key)
        ciphertext = payload_cipher.encrypt(
            payload_nonce,
            plaintext_bytes,
            header_bytes,
        )

        # 7) Wrap payload key
        wrap_cipher = ChaCha20Poly1305(wrap_key)
        wrapped_key = wrap_cipher.encrypt(
            wrap_nonce,
            payload_key,
            header_bytes,
        )

        # 8) Unsigned envelope
        unsigned_envelope = {
            "header": header,
            "wrapped_key": cls._b64encode(wrapped_key),
            "ciphertext": cls._b64encode(ciphertext),
        }

        # 9) Sign envelope
        signature_b64 = cls._sign_canonical_object(
            sender_ed25519_private_b64,
            unsigned_envelope,
        )

        envelope = {
            **unsigned_envelope,
            "signature": {
                "algorithm": "Ed25519",
                "value": signature_b64,
            },
        }

        result = {"envelope": envelope}

        if include_debug:
            result["debug"] = {
                "payload_key_b64": cls._b64encode(payload_key),
                "payload_nonce_b64": cls._b64encode(payload_nonce),
                "ephemeral_private_key_b64": eph.private_key_b64,
                "ephemeral_public_key_b64": eph.public_key_b64,
                "shared_secret_b64": cls._b64encode(shared_secret),
                "salt_wrap_b64": cls._b64encode(salt_wrap),
                "wrap_key_b64": cls._b64encode(wrap_key),
                "wrap_nonce_b64": cls._b64encode(wrap_nonce),
                "wrapped_key_b64": cls._b64encode(wrapped_key),
                "plaintext_sha256": hashlib.sha256(plaintext_bytes).hexdigest(),
            }

        return result

    @classmethod
    def decrypt_message(
        cls,
        receiver_profile: JsonDict,
        envelope: JsonDict,
        sender_contact: Optional[JsonDict] = None,
        verify_before_decrypt: bool = True,
        include_debug: bool = True,
    ) -> JsonDict:
        """
        Verify + decrypt envelope.

        verify_before_decrypt=True:
          - verify signature trước
          - nếu fail -> raise SignatureVerificationError

        sender_contact:
          - nếu truyền vào, service sẽ check envelope sender public key có khớp contact không

        Returns:
            {
              "plaintext": "...utf8 nếu decode được, không thì bytes ở key plaintext_bytes_b64",
              "verified": True,
              "debug": {...} # nếu include_debug=True
            }
        """
        cls._validate_envelope(envelope)

        header = envelope["header"]
        unsigned_envelope = {
            "header": envelope["header"],
            "wrapped_key": envelope["wrapped_key"],
            "ciphertext": envelope["ciphertext"],
        }

        sender_pub_from_envelope = header["sender"]["ed25519_public_key"]

        if sender_contact is not None:
            sender_pub_from_contact = cls._get_ed25519_public_key_b64(sender_contact)
            if sender_pub_from_contact != sender_pub_from_envelope:
                raise SignatureVerificationError(
                    "Sender public key in envelope does not match provided contact."
                )

        verified = False
        if verify_before_decrypt:
            verified = cls._verify_canonical_object(
                public_key_b64=sender_pub_from_envelope,
                obj=unsigned_envelope,
                signature_b64=envelope["signature"]["value"],
            )
            if not verified:
                raise SignatureVerificationError("Envelope signature is invalid.")

        receiver_x25519_private_b64 = cls._get_x25519_private_key_b64(receiver_profile)
        eph_public_b64 = header["crypto"]["ephemeral_x25519_public_key"]
        salt_wrap = cls._b64decode(header["crypto"]["salt_wrap"])
        payload_nonce = cls._b64decode(header["crypto"]["payload_nonce"])
        wrapped_key = cls._b64decode(envelope["wrapped_key"])
        ciphertext = cls._b64decode(envelope["ciphertext"])

        # 1) Derive shared secret
        shared_secret = derive_shared_secret_from_b64(
            private_key_b64=receiver_x25519_private_b64,
            peer_public_key_b64=eph_public_b64,
        )

        # 2) HKDF -> wrap_key + wrap_nonce
        wrap_key, wrap_nonce = cls._derive_wrap_material(shared_secret, salt_wrap)

        # 3) Unwrap payload key
        header_bytes = cls._canonical_json_bytes(header)
        wrap_cipher = ChaCha20Poly1305(wrap_key)
        payload_key = wrap_cipher.decrypt(
            wrap_nonce,
            wrapped_key,
            header_bytes,
        )

        # 4) Decrypt payload
        payload_cipher = ChaCha20Poly1305(payload_key)
        plaintext_bytes = payload_cipher.decrypt(
            payload_nonce,
            ciphertext,
            header_bytes,
        )

        result: JsonDict = {
            "verified": verified if verify_before_decrypt else None,
            "message_hash_sha256": hashlib.sha256(plaintext_bytes).hexdigest(),
        }

        try:
            result["plaintext"] = plaintext_bytes.decode("utf-8")
        except UnicodeDecodeError:
            result["plaintext_bytes_b64"] = cls._b64encode(plaintext_bytes)

        if include_debug:
            result["debug"] = {
                "shared_secret_b64": cls._b64encode(shared_secret),
                "wrap_key_b64": cls._b64encode(wrap_key),
                "wrap_nonce_b64": cls._b64encode(wrap_nonce),
                "payload_key_b64": cls._b64encode(payload_key),
                "payload_nonce_b64": cls._b64encode(payload_nonce),
                "wrapped_key_b64": envelope["wrapped_key"],
            }

        return result

    # =========================
    # Helpers - key extraction
    # =========================

    @staticmethod
    def _get_name(data: JsonDict) -> str:
        return str(
            data.get("name")
            or data.get("profile_name")
            or data.get("contact_name")
            or "unknown"
        )

    @staticmethod
    def _first_non_empty(*values: Any) -> str:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value
        raise InvalidProfileError("Required key material not found.")

    @classmethod
    def _get_ed25519_private_key_b64(cls, profile: JsonDict) -> str:
        ed = profile.get("ed25519", {})
        return cls._first_non_empty(
            ed.get("private_key"),
            ed.get("private"),
            profile.get("ed25519_private_key"),
            profile.get("signing_private_key"),
        )

    @classmethod
    def _get_ed25519_public_key_b64(cls, profile_or_contact: JsonDict) -> str:
        ed = profile_or_contact.get("ed25519", {})
        return cls._first_non_empty(
            ed.get("public_key"),
            ed.get("public"),
            profile_or_contact.get("ed25519_public_key"),
            profile_or_contact.get("signing_public_key"),
        )

    @classmethod
    def _get_x25519_private_key_b64(cls, profile: JsonDict) -> str:
        x = profile.get("x25519", {})
        return cls._first_non_empty(
            x.get("private_key"),
            x.get("private"),
            profile.get("x25519_private_key"),
            profile.get("kex_private_key"),
        )

    @classmethod
    def _get_x25519_public_key_b64(cls, profile_or_contact: JsonDict) -> str:
        x = profile_or_contact.get("x25519", {})
        return cls._first_non_empty(
            x.get("public_key"),
            x.get("public"),
            profile_or_contact.get("x25519_public_key"),
            profile_or_contact.get("kex_public_key"),
        )

    # =========================
    # Helpers - ed25519 load
    # =========================

    @staticmethod
    def _load_ed25519_private_key_from_b64(private_key_b64: str) -> Ed25519PrivateKey:
        raw = CryptoService._b64decode(private_key_b64)
        if len(raw) != 32:
            raise InvalidProfileError("Ed25519 private key must be 32 bytes.")
        return Ed25519PrivateKey.from_private_bytes(raw)

    @staticmethod
    def _load_ed25519_public_key_from_b64(public_key_b64: str) -> Ed25519PublicKey:
        raw = CryptoService._b64decode(public_key_b64)
        if len(raw) != 32:
            raise InvalidProfileError("Ed25519 public key must be 32 bytes.")
        return Ed25519PublicKey.from_public_bytes(raw)

    # =========================
    # Helpers - sign/verify object
    # =========================

    @classmethod
    def _sign_canonical_object(cls, private_key_b64: str, obj: JsonDict) -> str:
        private_key = cls._load_ed25519_private_key_from_b64(private_key_b64)
        data = cls._canonical_json_bytes(obj)
        signature = private_key.sign(data)
        return cls._b64encode(signature)

    @classmethod
    def _verify_canonical_object(
        cls,
        public_key_b64: str,
        obj: JsonDict,
        signature_b64: str,
    ) -> bool:
        public_key = cls._load_ed25519_public_key_from_b64(public_key_b64)
        data = cls._canonical_json_bytes(obj)
        signature = cls._b64decode(signature_b64)
        try:
            public_key.verify(signature, data)
            return True
        except Exception:
            return False

    # =========================
    # Helpers - HKDF
    # =========================

    @classmethod
    def _derive_wrap_material(cls, shared_secret: bytes, salt_wrap: bytes) -> Tuple[bytes, bytes]:
        """
        Từ shared_secret sinh ra:
        - wrap_key: 32 bytes
        - wrap_nonce: 12 bytes
        """
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=cls.HKDF_OUT_LEN,
            salt=salt_wrap,
            info=cls.WRAP_INFO,
        )
        material = hkdf.derive(shared_secret)
        wrap_key = material[: cls.PAYLOAD_KEY_LEN]
        wrap_nonce = material[cls.PAYLOAD_KEY_LEN : cls.PAYLOAD_KEY_LEN + cls.CHACHA20_NONCE_LEN]
        return wrap_key, wrap_nonce

    # =========================
    # Helpers - envelope validation
    # =========================

    @classmethod
    def _validate_envelope(cls, envelope: JsonDict) -> None:
        if not isinstance(envelope, dict):
            raise EnvelopeError("Envelope must be a dict.")

        required_top = ("header", "wrapped_key", "ciphertext", "signature")
        for key in required_top:
            if key not in envelope:
                raise EnvelopeError(f"Envelope missing field: {key}")

        header = envelope["header"]
        if not isinstance(header, dict):
            raise EnvelopeError("Envelope header must be a dict.")

        for key in ("sender", "receiver", "crypto", "version", "suite"):
            if key not in header:
                raise EnvelopeError(f"Envelope header missing field: {key}")

        sender = header["sender"]
        crypto = header["crypto"]
        signature = envelope["signature"]

        if "ed25519_public_key" not in sender:
            raise EnvelopeError("Envelope sender missing ed25519_public_key.")

        if "ephemeral_x25519_public_key" not in crypto:
            raise EnvelopeError("Envelope crypto missing ephemeral_x25519_public_key.")
        if "salt_wrap" not in crypto:
            raise EnvelopeError("Envelope crypto missing salt_wrap.")
        if "payload_nonce" not in crypto:
            raise EnvelopeError("Envelope crypto missing payload_nonce.")

        if not isinstance(signature, dict) or "value" not in signature:
            raise EnvelopeError("Envelope signature format invalid.")

    # =========================
    # Helpers - util
    # =========================

    @staticmethod
    def _to_bytes(data: BytesOrStr) -> bytes:
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")
        raise TypeError("Expected bytes or str.")

    @staticmethod
    def _b64encode(data: bytes) -> str:
        return base64.b64encode(data).decode("utf-8")

    @staticmethod
    def _b64decode(data_b64: str) -> bytes:
        try:
            return base64.b64decode(data_b64.encode("utf-8"), validate=True)
        except Exception as exc:
            raise InvalidProfileError("Invalid base64 data.") from exc

    @staticmethod
    def _canonical_json_bytes(obj: Any) -> bytes:
        """
        Serialize ổn định để sign/verify.
        """
        return json.dumps(
            obj,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def _safe_fingerprint(public_key_b64: str) -> str:
        try:
            return key_fingerprint_from_public_key_b64(public_key_b64)
        except Exception:
            return "invalid"
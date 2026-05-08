from __future__ import annotations

import base64
import json
from typing import Any, Dict


JsonDict = Dict[str, Any]


class EnvelopeError(Exception):
    """Raised when envelope format is invalid."""


def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def b64d(data_b64: str) -> bytes:
    try:
        return base64.b64decode(data_b64.encode("utf-8"), validate=True)
    except Exception as exc:
        raise EnvelopeError("Invalid base64 data in envelope.") from exc


def canonical_dumps(obj: Any) -> bytes:
    """
    Serialize ổn định để:
    - sign / verify
    - dùng làm AAD
    """
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def build_header(
    *,
    version: int,
    suite: str,
    sender_name: str,
    sender_sig_public_b64: str,
    sender_sig_fingerprint: str,
    recipient_name: str,
    recipient_x25519_fingerprint: str,
    ephemeral_x25519_public_b64: str,
    ephemeral_x25519_fingerprint: str,
    salt_wrap_b64: str,
    msg_id_b64: str,
    payload_nonce_b64: str,
    expires_in: int = 300,
    created_at: str,
) -> JsonDict:
    """
    Tạo header chuẩn cho message envelope.
    """
    header: JsonDict = {
        "version": version,
        "suite": suite,
        "message_id": msg_id_b64,
        "expires_in": expires_in,
        "created_at": created_at,
        "sender": {
            "name": sender_name,
            "ed25519_public_key": sender_sig_public_b64,
            "ed25519_fingerprint": sender_sig_fingerprint,
        },
        "receiver": {
            "name": recipient_name,
            "x25519_fingerprint": recipient_x25519_fingerprint,
        },
        "crypto": {
            "ephemeral_x25519_public_key": ephemeral_x25519_public_b64,
            "ephemeral_x25519_fingerprint": ephemeral_x25519_fingerprint,
            "salt_wrap": salt_wrap_b64,
            "payload_nonce": payload_nonce_b64,
        },
    }

    if created_at is not None:
        header["created_at"] = created_at    
    return header


def build_header_bytes(header: JsonDict) -> bytes:
    """
    Header canonical bytes để:
    - làm AAD khi encrypt/decrypt
    - nằm trong dữ liệu được ký
    """
    validate_header(header)
    return canonical_dumps(header)


def build_unsigned_envelope(
    *,
    header: JsonDict,
    wrapped_key: bytes,
    ciphertext: bytes,
) -> JsonDict:
    """
    Envelope chưa có signature.
    """
    validate_header(header)

    return {
        "header": header,
        "wrapped_key": b64e(wrapped_key),
        "ciphertext": b64e(ciphertext),
    }


def build_signed_envelope(
    *,
    header: JsonDict,
    wrapped_key: bytes,
    ciphertext: bytes,
    signature: bytes,
    signature_algorithm: str = "Ed25519",
) -> JsonDict:
    """
    Envelope hoàn chỉnh có signature.
    """
    unsigned_envelope = build_unsigned_envelope(
        header=header,
        wrapped_key=wrapped_key,
        ciphertext=ciphertext,
    )

    return {
        **unsigned_envelope,
        "signature": {
            "algorithm": signature_algorithm,
            "value": b64e(signature),
        },
    }


def extract_unsigned_envelope(envelope: JsonDict) -> JsonDict:
    """
    Tách phần unsigned của envelope để verify signature.
    """
    validate_envelope(envelope)

    return {
        "header": envelope["header"],
        "wrapped_key": envelope["wrapped_key"],
        "ciphertext": envelope["ciphertext"],
    }


def build_signing_bytes(
    *,
    header: JsonDict,
    wrapped_key: bytes,
    ciphertext: bytes,
) -> bytes:
    """
    Dữ liệu raw bytes để sign/verify theo kiểu:
      header_bytes || wrapped_key || ciphertext
    """
    header_bytes = build_header_bytes(header)
    return header_bytes + wrapped_key + ciphertext


def build_signing_bytes_from_envelope(envelope: JsonDict) -> bytes:
    """
    Dùng khi verify envelope đã nhận.
    """
    validate_envelope(envelope)

    header = envelope["header"]
    wrapped_key = b64d(envelope["wrapped_key"])
    ciphertext = b64d(envelope["ciphertext"])

    return build_signing_bytes(
        header=header,
        wrapped_key=wrapped_key,
        ciphertext=ciphertext,
    )


def get_signature_bytes(envelope: JsonDict) -> bytes:
    validate_envelope(envelope)
    return b64d(envelope["signature"]["value"])


def get_wrapped_key_bytes(envelope: JsonDict) -> bytes:
    validate_envelope(envelope)
    return b64d(envelope["wrapped_key"])


def get_ciphertext_bytes(envelope: JsonDict) -> bytes:
    validate_envelope(envelope)
    return b64d(envelope["ciphertext"])


def get_payload_nonce_bytes(header: JsonDict) -> bytes:
    validate_header(header)
    return b64d(header["crypto"]["payload_nonce"])


def get_salt_wrap_bytes(header: JsonDict) -> bytes:
    validate_header(header)
    return b64d(header["crypto"]["salt_wrap"])


def get_ephemeral_public_key_b64(header: JsonDict) -> str:
    validate_header(header)
    return header["crypto"]["ephemeral_x25519_public_key"]


def get_sender_ed25519_public_key_b64(header: JsonDict) -> str:
    validate_header(header)
    return header["sender"]["ed25519_public_key"]


def get_message_id_b64(header: JsonDict) -> str:
    validate_header(header)
    return header["message_id"]


def validate_header(header: JsonDict) -> None:
    if not isinstance(header, dict):
        raise EnvelopeError("Header must be a dict.")

    required_top = ("version", "suite", "message_id","created_id", "expires_in", "sender", "receiver", "crypto")
    for key in required_top:
        if key not in header:
            raise EnvelopeError(f"Header missing field: {key}")

    sender = header["sender"]
    receiver = header["receiver"]
    crypto = header["crypto"]

    if not isinstance(sender, dict):
        raise EnvelopeError("Header field 'sender' must be a dict.")
    if not isinstance(receiver, dict):
        raise EnvelopeError("Header field 'receiver' must be a dict.")
    if not isinstance(crypto, dict):
        raise EnvelopeError("Header field 'crypto' must be a dict.")

    sender_required = ("name", "ed25519_public_key", "ed25519_fingerprint")
    for key in sender_required:
        if key not in sender:
            raise EnvelopeError(f"Header sender missing field: {key}")

    receiver_required = ("name", "x25519_fingerprint")
    for key in receiver_required:
        if key not in receiver:
            raise EnvelopeError(f"Header receiver missing field: {key}")

    crypto_required = (
        "ephemeral_x25519_public_key",
        "ephemeral_x25519_fingerprint",
        "salt_wrap",
        "payload_nonce",
    )
    for key in crypto_required:
        if key not in crypto:
            raise EnvelopeError(f"Header crypto missing field: {key}")


def validate_envelope(envelope: JsonDict) -> None:
    if not isinstance(envelope, dict):
        raise EnvelopeError("Envelope must be a dict.")

    required_top = ("header", "wrapped_key", "ciphertext", "signature")
    for key in required_top:
        if key not in envelope:
            raise EnvelopeError(f"Envelope missing field: {key}")

    validate_header(envelope["header"])

    if not isinstance(envelope["wrapped_key"], str) or not envelope["wrapped_key"].strip():
        raise EnvelopeError("Envelope field 'wrapped_key' must be a non-empty base64 string.")

    if not isinstance(envelope["ciphertext"], str) or not envelope["ciphertext"].strip():
        raise EnvelopeError("Envelope field 'ciphertext' must be a non-empty base64 string.")

    signature = envelope["signature"]
    if not isinstance(signature, dict):
        raise EnvelopeError("Envelope field 'signature' must be a dict.")

    if "algorithm" not in signature:
        raise EnvelopeError("Envelope signature missing field: algorithm.")
    if "value" not in signature:
        raise EnvelopeError("Envelope signature missing field: value.")

    if not isinstance(signature["value"], str) or not signature["value"].strip():
        raise EnvelopeError("Envelope signature value must be a non-empty base64 string.")


def extract_meta(envelope: JsonDict) -> JsonDict:
    """
    Trả metadata gọn cho UI/CLI.
    """
    validate_envelope(envelope)
    header = envelope["header"]

    return {
        "version": header["version"],
        "suite": header["suite"],
        "message_id": header["message_id"],
        "created_at": header["created_at"],
        "expires_in": header["expires_in"],
        "sender_name": header["sender"]["name"],
        "sender_ed25519_fingerprint": header["sender"]["ed25519_fingerprint"],
        "recipient_name": header["receiver"]["name"],
        "recipient_x25519_fingerprint": header["receiver"]["x25519_fingerprint"],
        "ephemeral_x25519_fingerprint": header["crypto"]["ephemeral_x25519_fingerprint"],
        "has_signature": True,
    }
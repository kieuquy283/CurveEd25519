from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519

from app.aead import decrypt_aead, encrypt_aead
from app.contacts import (
    get_contact_ed25519_public_bytes,
    get_contact_x25519_public_bytes,
    load_contact,
)
from app.kdf import derive_wrap_key_and_nonce
from app.keygen import (
    load_ed25519_private_key,
    load_profile_public_info,
    load_x25519_private_key,
)
from app.signer import sign_bytes, verify_bytes
from app.utils import APP_VERSION, SUITE_NAME, b64d, b64e, canonical_dumps, read_json, write_json


def _public_key_raw_bytes(pubkey: Any) -> bytes:
    return pubkey.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _build_header(
    sender_name: str,
    sender_sig_public_raw: bytes,
    recipient_name: str,
    recipient_kid: bytes,
    ephemeral_x25519_public_raw: bytes,
    salt_wrap: bytes,
    msg_id: bytes,
    payload_nonce: bytes,
) -> dict[str, Any]:
    return {
        "version": APP_VERSION,
        "suite": SUITE_NAME,
        "sender_name": sender_name,
        "sender_sig_public_b64": b64e(sender_sig_public_raw),
        "recipient_name": recipient_name,
        "recipient_kid_b64": b64e(recipient_kid),
        "ephemeral_x25519_public_b64": b64e(ephemeral_x25519_public_raw),
        "salt_wrap_b64": b64e(salt_wrap),
        "msg_id_b64": b64e(msg_id),
        "payload_nonce_b64": b64e(payload_nonce),
    }


def _build_header_bytes(header: dict[str, Any]) -> bytes:
    return canonical_dumps(header)


def encrypt_and_sign_message(
    data_dir: Path,
    sender_profile: str,
    recipient_contact_name: str,
    plaintext: bytes,
    out_path: Path,
) -> Path:
    # Sender keys
    sender_sig_priv = load_ed25519_private_key(data_dir, sender_profile)
    sender_info = load_profile_public_info(data_dir, sender_profile)
    sender_sig_public_raw = b64d(sender_info["ed25519_public_b64"])

    # Recipient public contact
    recipient_contact = load_contact(data_dir, recipient_contact_name)
    recipient_x25519_public_raw = get_contact_x25519_public_bytes(recipient_contact)
    recipient_x25519_public = x25519.X25519PublicKey.from_public_bytes(recipient_x25519_public_raw)
    recipient_kid = b64d(recipient_contact["x25519_fingerprint_b64"])

    # Random values
    payload_key = os.urandom(32)
    payload_nonce = os.urandom(12)
    salt_wrap = os.urandom(16)
    msg_id = os.urandom(16)

    # Ephemeral X25519
    eph_priv = x25519.X25519PrivateKey.generate()
    eph_pub = eph_priv.public_key()
    eph_pub_raw = _public_key_raw_bytes(eph_pub)

    # Header before payload encryption
    header = _build_header(
        sender_name=sender_profile,
        sender_sig_public_raw=sender_sig_public_raw,
        recipient_name=recipient_contact_name,
        recipient_kid=recipient_kid,
        ephemeral_x25519_public_raw=eph_pub_raw,
        salt_wrap=salt_wrap,
        msg_id=msg_id,
        payload_nonce=payload_nonce,
    )
    header_bytes = _build_header_bytes(header)

    # Encrypt payload
    ciphertext = encrypt_aead(payload_key, payload_nonce, plaintext, header_bytes)

    # X25519 shared secret
    shared_secret = eph_priv.exchange(recipient_x25519_public)

    # HKDF info
    hkdf_info = (
        b"curveapp-wrap-v1|"
        + sender_profile.encode("utf-8")
        + b"|"
        + recipient_contact_name.encode("utf-8")
        + b"|"
        + msg_id
    )

    wrap_key, wrap_nonce = derive_wrap_key_and_nonce(shared_secret, salt_wrap, hkdf_info)

    # Wrap payload key
    wrapped_key = encrypt_aead(wrap_key, wrap_nonce, payload_key, header_bytes)

    # Sign header + wrapped_key + ciphertext
    to_sign = header_bytes + wrapped_key + ciphertext
    signature = sign_bytes(sender_sig_priv, to_sign)

    envelope = {
        "header": header,
        "wrapped_key_b64": b64e(wrapped_key),
        "ciphertext_b64": b64e(ciphertext),
        "signature_b64": b64e(signature),
    }

    write_json(out_path, envelope)
    return out_path


def verify_and_decrypt_message(
    data_dir: Path,
    recipient_profile: str,
    envelope_path: Path,
    trusted_sender_contact_name: str | None = None,
) -> tuple[bytes, dict[str, Any]]:
    envelope = read_json(envelope_path)

    header = envelope["header"]
    wrapped_key = b64d(envelope["wrapped_key_b64"])
    ciphertext = b64d(envelope["ciphertext_b64"])
    signature = b64d(envelope["signature_b64"])

    header_bytes = _build_header_bytes(header)

    # Sender public key from envelope
    sender_sig_public_raw = b64d(header["sender_sig_public_b64"])
    sender_sig_public = ed25519.Ed25519PublicKey.from_public_bytes(sender_sig_public_raw)

    # Optional trust check against imported contact
    if trusted_sender_contact_name is not None:
        trusted = load_contact(data_dir, trusted_sender_contact_name)
        trusted_pub = get_contact_ed25519_public_bytes(trusted)
        if trusted_pub != sender_sig_public_raw:
            raise ValueError("Sender public key in envelope does not match trusted contact.")

    # Verify signature first
    to_verify = header_bytes + wrapped_key + ciphertext
    if not verify_bytes(sender_sig_public, to_verify, signature):
        raise ValueError("Invalid signature. Message may have been tampered with.")

    # Recipient private key
    recipient_x_priv = load_x25519_private_key(data_dir, recipient_profile)

    eph_pub_raw = b64d(header["ephemeral_x25519_public_b64"])
    eph_pub = x25519.X25519PublicKey.from_public_bytes(eph_pub_raw)

    salt_wrap = b64d(header["salt_wrap_b64"])
    msg_id = b64d(header["msg_id_b64"])
    payload_nonce = b64d(header["payload_nonce_b64"])

    shared_secret = recipient_x_priv.exchange(eph_pub)

    hkdf_info = (
        b"curveapp-wrap-v1|"
        + header["sender_name"].encode("utf-8")
        + b"|"
        + header["recipient_name"].encode("utf-8")
        + b"|"
        + msg_id
    )
    wrap_key, wrap_nonce = derive_wrap_key_and_nonce(shared_secret, salt_wrap, hkdf_info)

    payload_key = decrypt_aead(wrap_key, wrap_nonce, wrapped_key, header_bytes)
    plaintext = decrypt_aead(payload_key, payload_nonce, ciphertext, header_bytes)

    meta = {
        "sender_name": header["sender_name"],
        "recipient_name": header["recipient_name"],
        "suite": header["suite"],
        "msg_id_b64": header["msg_id_b64"],
        "signature_valid": True,
    }
    return plaintext, meta


def detached_sign_file(data_dir: Path, signer_profile: str, file_path: Path, sig_out: Path) -> Path:
    priv = load_ed25519_private_key(data_dir, signer_profile)
    data = file_path.read_bytes()
    signature = sign_bytes(priv, data)

    payload = {
        "signer_profile": signer_profile,
        "signature_b64": b64e(signature),
    }
    write_json(sig_out, payload)
    return sig_out


def detached_verify_file(
    data_dir: Path,
    contact_name: str,
    file_path: Path,
    sig_path: Path,
) -> bool:
    contact = load_contact(data_dir, contact_name)
    pub_raw = get_contact_ed25519_public_bytes(contact)
    pub = ed25519.Ed25519PublicKey.from_public_bytes(pub_raw)

    sig_payload = read_json(sig_path)
    signature = b64d(sig_payload["signature_b64"])
    data = file_path.read_bytes()

    return verify_bytes(pub, data, signature)
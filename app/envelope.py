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
from app.logger import info, kv, step, success, warning
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
    step("Encrypt pipeline started")

    # Sender keys
    info("Loading sender signing key")
    sender_sig_priv = load_ed25519_private_key(data_dir, sender_profile)

    info("Loading sender public profile info")
    sender_info = load_profile_public_info(data_dir, sender_profile)
    sender_sig_public_raw = b64d(sender_info["ed25519_public_b64"])

    # Recipient public contact
    info("Loading recipient contact")
    recipient_contact = load_contact(data_dir, recipient_contact_name)
    recipient_x25519_public_raw = get_contact_x25519_public_bytes(recipient_contact)
    recipient_x25519_public = x25519.X25519PublicKey.from_public_bytes(
        recipient_x25519_public_raw
    )
    recipient_kid = b64d(recipient_contact["x25519_fingerprint_b64"])

    kv("Sender", sender_profile)
    kv("Recipient", recipient_contact_name)
    kv("Plaintext length", f"{len(plaintext)} bytes")

    # Random values
    info("Generating random payload key, nonce, salt, and message id")
    payload_key = os.urandom(32)
    payload_nonce = os.urandom(12)
    salt_wrap = os.urandom(16)
    msg_id = os.urandom(16)

    kv("Payload key length", "32 bytes")
    kv("Payload nonce length", "12 bytes")
    kv("Wrap salt length", "16 bytes")
    kv("Message ID length", "16 bytes")

    # Ephemeral X25519
    info("Generating ephemeral X25519 keypair")
    eph_priv = x25519.X25519PrivateKey.generate()
    eph_pub = eph_priv.public_key()
    eph_pub_raw = _public_key_raw_bytes(eph_pub)
    kv("Ephemeral public key length", f"{len(eph_pub_raw)} bytes")

    # Header before payload encryption
    info("Building canonical header")
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
    kv("Header length", f"{len(header_bytes)} bytes")

    # Encrypt payload
    info("Encrypting plaintext with ChaCha20-Poly1305")
    ciphertext = encrypt_aead(payload_key, payload_nonce, plaintext, header_bytes)
    kv("Ciphertext length", f"{len(ciphertext)} bytes")

    # X25519 shared secret
    info("Computing X25519 shared secret")
    shared_secret = eph_priv.exchange(recipient_x25519_public)
    kv("Shared secret length", f"{len(shared_secret)} bytes")

    # HKDF info
    info("Preparing HKDF context info")
    hkdf_info = (
        b"curveapp-wrap-v1|"
        + sender_profile.encode("utf-8")
        + b"|"
        + recipient_contact_name.encode("utf-8")
        + b"|"
        + msg_id
    )
    kv("HKDF info length", f"{len(hkdf_info)} bytes")

    info("Deriving wrap key and wrap nonce via HKDF-SHA256")
    wrap_key, wrap_nonce = derive_wrap_key_and_nonce(shared_secret, salt_wrap, hkdf_info)
    kv("Wrap key length", f"{len(wrap_key)} bytes")
    kv("Wrap nonce length", f"{len(wrap_nonce)} bytes")

    # Wrap payload key
    info("Wrapping payload key with ChaCha20-Poly1305")
    wrapped_key = encrypt_aead(wrap_key, wrap_nonce, payload_key, header_bytes)
    kv("Wrapped key length", f"{len(wrapped_key)} bytes")

    # Sign header + wrapped_key + ciphertext
    info("Signing message envelope with Ed25519")
    to_sign = header_bytes + wrapped_key + ciphertext
    signature = sign_bytes(sender_sig_priv, to_sign)
    kv("Signed payload length", f"{len(to_sign)} bytes")
    kv("Signature length", f"{len(signature)} bytes")

    envelope = {
        "header": header,
        "wrapped_key_b64": b64e(wrapped_key),
        "ciphertext_b64": b64e(ciphertext),
        "signature_b64": b64e(signature),
    }

    info("Writing encrypted JSON envelope to disk")
    write_json(out_path, envelope)

    success("Encrypt pipeline finished")
    kv("Envelope path", str(out_path))
    return out_path


def verify_and_decrypt_message(
    data_dir: Path,
    recipient_profile: str,
    envelope_path: Path,
    trusted_sender_contact_name: str | None = None,
) -> tuple[bytes, dict[str, Any]]:
    step("Decrypt pipeline started")

    info("Reading encrypted envelope from disk")
    envelope = read_json(envelope_path)

    header = envelope["header"]
    wrapped_key = b64d(envelope["wrapped_key_b64"])
    ciphertext = b64d(envelope["ciphertext_b64"])
    signature = b64d(envelope["signature_b64"])

    header_bytes = _build_header_bytes(header)

    kv("Envelope path", str(envelope_path))
    kv("Header length", f"{len(header_bytes)} bytes")
    kv("Wrapped key length", f"{len(wrapped_key)} bytes")
    kv("Ciphertext length", f"{len(ciphertext)} bytes")
    kv("Signature length", f"{len(signature)} bytes")

    # Sender public key from envelope
    info("Loading sender public key from envelope")
    sender_sig_public_raw = b64d(header["sender_sig_public_b64"])
    sender_sig_public = ed25519.Ed25519PublicKey.from_public_bytes(sender_sig_public_raw)

    # Optional trust check against imported contact
    if trusted_sender_contact_name is not None:
        info("Checking sender public key against trusted contact")
        trusted = load_contact(data_dir, trusted_sender_contact_name)
        trusted_pub = get_contact_ed25519_public_bytes(trusted)
        if trusted_pub != sender_sig_public_raw:
            raise ValueError("Sender public key in envelope does not match trusted contact.")
        success("Trusted sender key matched")
    else:
        warning("No trusted sender contact provided")

    # Verify signature first
    info("Verifying Ed25519 signature")
    to_verify = header_bytes + wrapped_key + ciphertext
    if not verify_bytes(sender_sig_public, to_verify, signature):
        raise ValueError("Invalid signature. Message may have been tampered with.")
    success("Signature verification passed")

    # Recipient private key
    info("Loading recipient X25519 private key")
    recipient_x_priv = load_x25519_private_key(data_dir, recipient_profile)

    info("Loading sender ephemeral X25519 public key")
    eph_pub_raw = b64d(header["ephemeral_x25519_public_b64"])
    eph_pub = x25519.X25519PublicKey.from_public_bytes(eph_pub_raw)

    salt_wrap = b64d(header["salt_wrap_b64"])
    msg_id = b64d(header["msg_id_b64"])
    payload_nonce = b64d(header["payload_nonce_b64"])

    kv("Recipient profile", recipient_profile)
    kv("Payload nonce length", f"{len(payload_nonce)} bytes")
    kv("Wrap salt length", f"{len(salt_wrap)} bytes")
    kv("Message ID length", f"{len(msg_id)} bytes")

    info("Computing X25519 shared secret")
    shared_secret = recipient_x_priv.exchange(eph_pub)
    kv("Shared secret length", f"{len(shared_secret)} bytes")

    info("Preparing HKDF context info")
    hkdf_info = (
        b"curveapp-wrap-v1|"
        + header["sender_name"].encode("utf-8")
        + b"|"
        + header["recipient_name"].encode("utf-8")
        + b"|"
        + msg_id
    )
    kv("HKDF info length", f"{len(hkdf_info)} bytes")

    info("Deriving wrap key and wrap nonce via HKDF-SHA256")
    wrap_key, wrap_nonce = derive_wrap_key_and_nonce(shared_secret, salt_wrap, hkdf_info)

    info("Unwrapping payload key")
    payload_key = decrypt_aead(wrap_key, wrap_nonce, wrapped_key, header_bytes)
    kv("Recovered payload key length", f"{len(payload_key)} bytes")

    info("Decrypting payload ciphertext")
    plaintext = decrypt_aead(payload_key, payload_nonce, ciphertext, header_bytes)
    kv("Recovered plaintext length", f"{len(plaintext)} bytes")

    success("Decrypt pipeline finished")

    meta = {
        "sender_name": header["sender_name"],
        "recipient_name": header["recipient_name"],
        "suite": header["suite"],
        "msg_id_b64": header["msg_id_b64"],
        "signature_valid": True,
    }
    return plaintext, meta


def detached_sign_file(
    data_dir: Path,
    signer_profile: str,
    file_path: Path,
    sig_out: Path,
) -> Path:
    step("Detached sign pipeline started")

    info("Loading signer private key")
    priv = load_ed25519_private_key(data_dir, signer_profile)

    info("Reading input file for detached signature")
    data = file_path.read_bytes()
    kv("Signer profile", signer_profile)
    kv("Input file", str(file_path))
    kv("Input size", f"{len(data)} bytes")

    info("Creating Ed25519 detached signature")
    signature = sign_bytes(priv, data)
    kv("Signature length", f"{len(signature)} bytes")

    payload = {
        "signer_profile": signer_profile,
        "signature_b64": b64e(signature),
    }

    info("Writing detached signature JSON")
    write_json(sig_out, payload)

    success("Detached signing finished")
    kv("Signature file", str(sig_out))
    return sig_out


def detached_verify_file(
    data_dir: Path,
    contact_name: str,
    file_path: Path,
    sig_path: Path,
) -> bool:
    step("Detached verify pipeline started")

    info("Loading trusted contact public key")
    contact = load_contact(data_dir, contact_name)
    pub_raw = get_contact_ed25519_public_bytes(contact)
    pub = ed25519.Ed25519PublicKey.from_public_bytes(pub_raw)

    info("Reading detached signature payload")
    sig_payload = read_json(sig_path)
    signature = b64d(sig_payload["signature_b64"])

    info("Reading original file")
    data = file_path.read_bytes()

    kv("Trusted contact", contact_name)
    kv("Input file", str(file_path))
    kv("Signature file", str(sig_path))
    kv("Input size", f"{len(data)} bytes")
    kv("Signature length", f"{len(signature)} bytes")

    info("Verifying Ed25519 signature")
    ok = verify_bytes(pub, data, signature)

    if ok:
        success("Detached signature verification passed")
    else:
        warning("Detached signature verification failed")

    return ok
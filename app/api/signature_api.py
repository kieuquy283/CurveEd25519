from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.crypto_service import CryptoService
from app.services.connection_service import ConnectionService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/signature", tags=["signature"])
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
ACCOUNTS_PATH = DATA_DIR / "accounts.json"
PROFILES_DIR = DATA_DIR / "profiles"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
if not ACCOUNTS_PATH.exists():
    ACCOUNTS_PATH.write_text("[]", encoding="utf-8")

connections = ConnectionService(
    connections_path=str(DATA_DIR / "connections.json"),
    accounts_path=str(ACCOUNTS_PATH),
    profiles_dir=str(PROFILES_DIR),
)
auth = AuthService(accounts_path=str(ACCOUNTS_PATH), profiles_dir=str(PROFILES_DIR))


def _log(message: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[signature_api][{ts}] {message}")


class SignFileRequest(BaseModel):
    signer: str
    filename: str
    mime_type: str
    content_b64: str


class VerifyFileRequest(BaseModel):
    signed_file: dict[str, Any]
    verifier: str | None = None


SIGNED_FIELDS = [
    "version",
    "type",
    "filename",
    "mimeType",
    "size",
    "content_b64",
    "signer",
    "signer_public_key",
    "algorithm",
    "hash",
    "signed_at",
]


def _resolve_account(identifier: str) -> dict[str, Any]:
    needle = identifier.strip().lower()
    accounts = auth._load_accounts()
    for account in accounts:
        email = str(account.get("email") or "").strip().lower()
        user_id = str(account.get("user_id") or email).strip().lower()
        if needle in {email, user_id}:
            if "user_id" not in account:
                account["user_id"] = user_id
                auth._save_accounts(accounts)
            return account
    raise HTTPException(
        status_code=404,
        detail={
            "detail": "Account not found. Please register and verify this email first.",
            "normalized_user": needle,
            "account_exists": False,
            "profile_exists": False,
        },
    )


def _ensure_profile_for_account(account: dict[str, Any]) -> dict[str, Any]:
    email = str(account.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Signer account has no email.")

    profile = auth._ensure_profile_exists(email, str(account.get("display_name") or email))
    _log(f"profile auto-created for account email={email}")
    _validate_signing_profile(profile)
    return profile


def _validate_signing_profile(profile: dict[str, Any]) -> None:
    ed = profile.get("ed25519") or {}
    x = profile.get("x25519") or {}
    if not ed.get("private_key") or not ed.get("public_key") or not x.get("public_key"):
        raise HTTPException(status_code=404, detail="Signer profile or Ed25519 signing key not found.")


def _decode_b64(value: str) -> bytes:
    try:
        return base64.b64decode(value.encode("utf-8"), validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 content") from exc


def _canonical_payload_bytes(container: dict[str, Any]) -> bytes:
    canonical_obj = {field: container.get(field) for field in SIGNED_FIELDS}
    return json.dumps(canonical_obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _validate_container_fields(container: dict[str, Any]) -> None:
    for field in SIGNED_FIELDS + ["signature"]:
        if field not in container:
            raise HTTPException(status_code=400, detail=f"Missing field: {field}")


@router.post("/sign-file")
def sign_file(req: SignFileRequest):
    signer = req.signer.strip().lower()
    _log(f"sign-file lookup signer={signer}")
    if not signer:
        raise HTTPException(status_code=400, detail="Signer is required.")
    file_bytes = _decode_b64(req.content_b64)
    account = _resolve_account(signer)
    if not bool(account.get("verified")):
        raise HTTPException(status_code=403, detail="Account not verified. Please verify this email first.")
    profile = _ensure_profile_for_account(account)
    signer_public_key = CryptoService._get_ed25519_public_key_b64(profile)
    signer_private_key = CryptoService._get_ed25519_private_key_b64(profile)

    signed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    signed_file = {
        "version": 1,
        "type": "signed-file",
        "filename": req.filename,
        "mimeType": req.mime_type or "application/octet-stream",
        "size": len(file_bytes),
        "content_b64": req.content_b64,
        "signer": profile.get("username") or signer,
        "signer_public_key": signer_public_key,
        "algorithm": "Ed25519",
        "hash": "SHA-256",
        "signed_at": signed_at,
    }

    payload = _canonical_payload_bytes(signed_file)
    signature = CryptoService.sign_bytes(private_key_b64=signer_private_key, data=payload)
    signed_file["signature"] = base64.b64encode(signature).decode("utf-8")

    return {
        "ok": True,
        "signed_file": signed_file,
        "debug": {
            "algorithm": "Ed25519",
            "hash": "SHA-256",
            "payload_size": len(payload),
            "signature_size": len(signature),
            "signer": signed_file["signer"],
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
        },
    }


@router.get("/profile-status")
def profile_status(user: str):
    user_norm = user.strip().lower()
    _log(f"profile-status lookup normalized_email={user_norm}")
    try:
        account = _resolve_account(user_norm)
        account_exists = True
    except HTTPException:
        account = None
        account_exists = False

    profile = None
    if account:
        try:
            profile = _ensure_profile_for_account(account)
        except HTTPException:
            profile = None

    ed = (profile or {}).get("ed25519") or {}
    x = (profile or {}).get("x25519") or {}
    return {
        "ok": True,
        "user": user_norm,
        "account_exists": account_exists,
        "profile_exists": profile is not None,
        "has_ed25519_private_key": bool(ed.get("private_key")),
        "has_ed25519_public_key": bool(ed.get("public_key")),
        "has_x25519_private_key": bool(x.get("private_key")),
        "has_x25519_public_key": bool(x.get("public_key")),
    }


@router.post("/verify-file")
def verify_file(req: VerifyFileRequest):
    signed_file = req.signed_file

    _validate_container_fields(signed_file)
    _decode_b64(str(signed_file["content_b64"]))

    if signed_file.get("algorithm") != "Ed25519" or signed_file.get("hash") != "SHA-256":
        return {
            "ok": True,
            "valid": False,
            "message": "Thuật toán không hợp lệ.",
            "debug": {
                "algorithm": str(signed_file.get("algorithm")),
                "hash": str(signed_file.get("hash")),
                "signer": str(signed_file.get("signer")),
                "trusted": False,
            },
        }

    signer = str(signed_file.get("signer"))

    trusted = False
    trusted_public_key = str(signed_file.get("signer_public_key"))
    trusted_debug: dict[str, Any] = {}

    if req.verifier:
        try:
            trusted_contact = connections.resolve_trusted_contact_public_keys(owner=req.verifier, peer=signer)
            trusted_public_key = trusted_contact["ed25519_public_key"]
            trusted = True
            trusted_debug = {
                "trusted_connection": True,
                "signature_key_owner": signer,
                "ed25519_fingerprint": trusted_contact["ed25519_fingerprint"],
            }
        except ValueError:
            trusted = False

    payload = _canonical_payload_bytes(signed_file)
    signature_bytes = _decode_b64(str(signed_file["signature"]))
    valid = CryptoService.verify_bytes(public_key_b64=trusted_public_key, data=payload, signature=signature_bytes)

    if not valid:
        return {
            "ok": True,
            "valid": False,
            "message": "File đã bị thay đổi hoặc chữ ký không hợp lệ.",
            "debug": {
                "algorithm": "Ed25519",
                "hash": "SHA-256",
                "signer": signer,
                "trusted": trusted,
                **trusted_debug,
            },
        }

    return {
        "ok": True,
        "valid": True,
        "message": "Chữ ký hợp lệ. Nội dung chưa bị thay đổi.",
        "file": {
            "filename": str(signed_file["filename"]),
            "mime_type": str(signed_file["mimeType"]),
            "content_b64": str(signed_file["content_b64"]),
            "size": int(signed_file["size"]),
        },
        "debug": {
            "algorithm": "Ed25519",
            "hash": "SHA-256",
            "signer": signer,
            "trusted": trusted,
            **trusted_debug,
        },
    }

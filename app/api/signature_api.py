from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.crypto_service import CryptoService
from app.services.connection_service import ConnectionService

router = APIRouter(prefix="/api/signature", tags=["signature"])
connections = ConnectionService(
    connections_path="data/connections.json",
    accounts_path="data/accounts.json",
    profiles_dir="data/profiles",
)


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


def _load_profile_by_username(username: str) -> dict[str, Any]:
    normalized = username.strip().lower()
    for path in Path("data/profiles").glob("*.json"):
        profile = json.loads(path.read_text(encoding="utf-8"))
        profile_username = ((profile.get("username") or profile.get("name") or "").strip().lower())
        if profile_username == normalized:
            if "username" not in profile and profile.get("name"):
                profile["username"] = profile["name"]
            return profile
    raise HTTPException(status_code=404, detail=f"Profile not found: {username}")


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
    file_bytes = _decode_b64(req.content_b64)
    profile = _load_profile_by_username(req.signer)
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
        "signer": profile.get("username") or req.signer,
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

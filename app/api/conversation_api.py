from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
from pathlib import Path

from app.services.protocol_service import ProtocolService
from app.profiles.profile_service import ProfileService
from app.services.connection_service import ConnectionService

router = APIRouter(prefix="/api/conversation", tags=["conversation"])

protocol = ProtocolService()
profiles = ProfileService()
connections = ConnectionService(
    connections_path="data/connections.json",
    accounts_path="data/accounts.json",
    profiles_dir="data/profiles",
)


class EncryptRequest(BaseModel):
    sender: str
    recipient: str
    plaintext: str


class DecryptRequest(BaseModel):
    receiver: str
    sender: str
    envelope: dict


class EncryptFileRequest(BaseModel):
    sender: str
    recipient: str
    filename: str
    mime_type: str
    content_b64: str


def get_profile(username: str):
    username = username.strip().lower()

    for path in Path("data/profiles").glob("*.json"):
        with path.open("r", encoding="utf-8") as f:
            profile = json.load(f)

        profile_username = ((profile.get("username") or profile.get("name") or "").strip().lower())

        if profile_username == username:
            if "username" not in profile and profile.get("name"):
                profile["username"] = profile.get("name")

            if "display_name" not in profile:
                profile["display_name"] = profile.get("display_name") or profile.get("username") or profile.get("name")

            return profile

    raise HTTPException(status_code=404, detail=f"Profile not found: {username}")


def profile_to_contact(profile: dict):
    uname = profile.get("username") or profile.get("name") or profile.get("display_name")
    display = profile.get("display_name") or uname

    def _pub(key_type: str, public_field: str = "public_key"):
        obj = profile.get(key_type) or {}
        if isinstance(obj, dict) and obj.get(public_field):
            return obj[public_field]
        return profile.get(f"{key_type}_{public_field}")

    return {
        "username": uname,
        "display_name": display,
        "ed25519": {"public_key": _pub("ed25519")},
        "x25519": {"public_key": _pub("x25519")},
    }


def _require_trusted(owner: str, peer: str) -> dict:
    try:
        return connections.resolve_trusted_contact_public_keys(owner=owner, peer=peer)
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail="Bạn cần xác minh kết nối và trao đổi khóa công khai trước khi gửi tin mã hóa.",
        ) from exc


@router.post("/encrypt")
def encrypt_message(req: EncryptRequest):
    trusted = _require_trusted(req.sender, req.recipient)

    sender_profile = get_profile(req.sender)
    recipient_profile = get_profile(req.recipient)
    recipient_contact = profile_to_contact(recipient_profile)
    recipient_contact["x25519"]["public_key"] = trusted["x25519_public_key"]
    recipient_contact["ed25519"]["public_key"] = trusted["ed25519_public_key"]

    result = protocol.send_message(
        sender_profile=sender_profile,
        receiver_contact=recipient_contact,
        plaintext=req.plaintext,
        include_debug=True,
    )

    return {
        "ok": True,
        "envelope": result["envelope"],
        "debug": {
            **(result.get("debug") or {}),
            "trusted_connection": True,
            "encryption_key_owner": trusted["peer_email"],
            "signature_key_owner": req.sender,
            "x25519_fingerprint": trusted["x25519_fingerprint"],
            "ed25519_fingerprint": trusted["ed25519_fingerprint"],
            "algorithms": ["X25519", "HKDF-SHA256", "ChaCha20-Poly1305", "Ed25519"],
        },
    }


@router.post("/encrypt-file")
def encrypt_file(req: EncryptFileRequest):
    if not req.content_b64 or not isinstance(req.content_b64, str):
        raise HTTPException(status_code=400, detail="content_b64 must be a non-empty base64 string")

    if req.mime_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Unsupported mime_type; only application/pdf is allowed")

    trusted = _require_trusted(req.sender, req.recipient)

    sender_profile = get_profile(req.sender)
    recipient_profile = get_profile(req.recipient)
    recipient_contact = profile_to_contact(recipient_profile)
    recipient_contact["x25519"]["public_key"] = trusted["x25519_public_key"]
    recipient_contact["ed25519"]["public_key"] = trusted["ed25519_public_key"]

    try:
        import base64

        content_bytes = base64.b64decode(req.content_b64.encode("utf-8"), validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="content_b64 is not valid base64")

    payload = {
        "type": "file",
        "filename": req.filename,
        "mime_type": req.mime_type,
        "content_b64": req.content_b64,
        "size": len(content_bytes),
    }

    plaintext = json.dumps(payload, ensure_ascii=False)

    result = protocol.send_message(
        sender_profile=sender_profile,
        receiver_contact=recipient_contact,
        plaintext=plaintext,
        include_debug=True,
    )

    envelope = result.get("envelope")

    try:
        ciphertext_b64 = envelope.get("ciphertext")
        from app.core.envelope import b64d

        ciphertext_size = len(b64d(ciphertext_b64))
    except Exception:
        ciphertext_size = None

    debug = {
        "plaintext_size": len(plaintext.encode("utf-8")),
        "ciphertext_size": ciphertext_size,
        "suite": ProtocolService.SUITE,
        "trusted_connection": True,
        "encryption_key_owner": trusted["peer_email"],
        "signature_key_owner": req.sender,
        "x25519_fingerprint": trusted["x25519_fingerprint"],
        "ed25519_fingerprint": trusted["ed25519_fingerprint"],
        "algorithms": ["X25519", "HKDF-SHA256", "ChaCha20-Poly1305", "Ed25519"],
    }

    if result.get("debug"):
        debug.update({k: v for k, v in result["debug"].items() if k != "payload_key_b64"})

    return {
        "ok": True,
        "envelope": envelope,
        "debug": debug,
    }


@router.post("/decrypt")
def decrypt_message(req: DecryptRequest):
    trusted = _require_trusted(req.receiver, req.sender)

    receiver_profile = get_profile(req.receiver)
    sender_profile = get_profile(req.sender)
    sender_contact = profile_to_contact(sender_profile)
    sender_contact["x25519"]["public_key"] = trusted["x25519_public_key"]
    sender_contact["ed25519"]["public_key"] = trusted["ed25519_public_key"]

    result = protocol.receive_message(
        receiver_profile=receiver_profile,
        sender_contact=sender_contact,
        envelope=req.envelope,
        include_debug=True,
    )

    response = {"ok": True}

    if "plaintext" in result:
        txt = result["plaintext"]
        parsed = None
        try:
            parsed = json.loads(txt)
        except Exception:
            parsed = None

        if isinstance(parsed, dict) and parsed.get("type") == "file":
            response["message"] = {
                "type": "file",
                "filename": parsed.get("filename"),
                "mime_type": parsed.get("mime_type"),
                "content_b64": parsed.get("content_b64"),
                "size": parsed.get("size"),
                "verified": result.get("verified", False),
            }
        else:
            response["plaintext"] = txt
    elif "plaintext_bytes_b64" in result:
        response["plaintext_bytes_b64"] = result["plaintext_bytes_b64"]

    if "debug" in result:
        response["debug"] = {
            **result["debug"],
            "trusted_connection": True,
            "encryption_key_owner": req.receiver,
            "signature_key_owner": req.sender,
            "x25519_fingerprint": trusted["x25519_fingerprint"],
            "ed25519_fingerprint": trusted["ed25519_fingerprint"],
            "algorithms": ["X25519", "HKDF-SHA256", "ChaCha20-Poly1305", "Ed25519"],
        }

    return response

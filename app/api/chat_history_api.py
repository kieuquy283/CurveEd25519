from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.storage_repository import StorageRepository

router = APIRouter(prefix="/api/conversations", tags=["chat-history"])
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
storage = StorageRepository(data_dir=str(DATA_DIR))


def _norm(email: str) -> str:
    return email.strip().lower()


class SaveMessageBody(BaseModel):
    sender_email: str
    receiver_email: str
    packet_id: str | None = None
    message_type: str = "text"
    ciphertext_envelope: dict[str, Any] | None = None
    plaintext_preview: str | None = None
    attachment_json: dict[str, Any] | None = None
    crypto_debug: dict[str, Any] | None = None
    status: str | None = None
    connection_id: str | None = None


@router.get("")
def list_conversations(user: str = Query(...)):
    user_norm = _norm(user)
    try:
        rows = storage.list_conversations(user_norm)
        return {"ok": True, "conversations": rows}
    except Exception as exc:
        return {
            "ok": True,
            "conversations": [],
            "warning": f"list_conversations_failed: {exc.__class__.__name__}",
        }


@router.get("/{conversation_id}/messages")
def list_messages(
    conversation_id: str,
    user: str = Query(...),
    limit: int = Query(50),
    before: str | None = Query(None),
):
    user_norm = _norm(user)
    try:
        rows = storage.list_messages(conversation_id, user_norm, limit=max(1, min(limit, 200)))
    except Exception as exc:
        return {
            "ok": True,
            "messages": [],
            "warning": f"list_messages_failed: {exc.__class__.__name__}",
        }
    if before:
        rows = [r for r in rows if str(r.get("created_at") or "") < before]
    return {"ok": True, "messages": rows}


@router.post("/{conversation_id}/messages/save")
def save_message(conversation_id: str, body: SaveMessageBody):
    sender = _norm(body.sender_email)
    receiver = _norm(body.receiver_email)

    try:
        conv = storage.get_or_create_conversation(sender, receiver, body.connection_id)
    except Exception as exc:
        return {"ok": False, "error": f"save_message_failed: {exc.__class__.__name__}"}

    if conv.get("id") != conversation_id:
        conversation_id = str(conv.get("id"))
    msg_id = body.packet_id or secrets.token_hex(12)
    created_at = datetime.now(timezone.utc).isoformat()
    record = {
        "id": msg_id,
        "conversation_id": conversation_id,
        "sender_email": sender,
        "receiver_email": receiver,
        "packet_id": body.packet_id,
        "message_type": body.message_type,
        "ciphertext_envelope": body.ciphertext_envelope,
        "plaintext_preview": body.plaintext_preview,
        "attachment_json": body.attachment_json,
        "crypto_debug": body.crypto_debug,
        "status": body.status or "sent",
        "created_at": created_at,
    }

    try:
        saved = storage.save_message(record)
    except Exception as exc:
        return {"ok": False, "error": f"save_message_failed: {exc.__class__.__name__}"}

    try:
        storage.create_notification(
            {
                "id": secrets.token_hex(12),
                "user_email": receiver,
                "type": "message",
                "title": sender,
                "body": (body.plaintext_preview or "").strip()[:120] or "Tin nhan moi",
                "data": {
                    "peerEmail": sender,
                    "conversationId": conversation_id,
                    "status": "message",
                },
                "read": False,
                "created_at": created_at,
            }
        )
    except Exception:
        pass

    return {"ok": True, "conversation_id": conversation_id, "message": saved}

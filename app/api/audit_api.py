from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.storage_repository import StorageRepository

router = APIRouter(prefix="/api/audit", tags=["audit"])
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
storage = StorageRepository(data_dir=str(DATA_DIR))


class AuditEventBody(BaseModel):
    user_email: str | None = None
    conversation_id: str | None = None
    message_id: str | None = None
    peer_email: str | None = None
    event_type: str
    created_at: str | None = None
    metadata: dict[str, Any] | None = None


def _norm_email(value: str | None) -> str | None:
    if value is None:
        return None
    norm = value.strip().lower()
    return norm or None


@router.post("/event")
def create_audit_event(body: AuditEventBody):
    event = {
        "id": secrets.token_hex(12),
        "user_email": _norm_email(body.user_email),
        "conversation_id": body.conversation_id,
        "message_id": body.message_id,
        "peer_email": _norm_email(body.peer_email),
        "event_type": str(body.event_type or "").strip(),
        "created_at": body.created_at or datetime.now(timezone.utc).isoformat(),
        "metadata": body.metadata or {},
    }

    if not event["event_type"]:
        return {"ok": False, "error": "event_type_required"}

    try:
        saved = storage.create_audit_event(event)
    except Exception as exc:
        return {"ok": False, "error": f"audit_event_failed: {exc.__class__.__name__}"}

    return {"ok": True, "event": saved}

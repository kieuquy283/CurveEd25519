from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
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


class WatermarkTraceBody(BaseModel):
    trace_code: str
    user_email: str
    conversation_id: str | None = None
    peer_email: str | None = None
    peer_display_name: str | None = None
    session_id: str
    time_window_start: str
    time_window_end: str


def _norm_email(value: str | None) -> str | None:
    if value is None:
        return None
    norm = value.strip().lower()
    return norm or None


def _extract_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    if request.client and request.client.host:
        return request.client.host
    return None


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


@router.post("/watermark-trace")
def create_watermark_trace(body: WatermarkTraceBody, request: Request):
    now = datetime.now(timezone.utc).isoformat()
    trace = str(body.trace_code or "").strip().upper()
    if not trace:
        return {"ok": False, "error": "trace_code_required"}

    event = {
        "id": secrets.token_hex(12),
        "user_email": _norm_email(body.user_email),
        "conversation_id": body.conversation_id,
        "peer_email": _norm_email(body.peer_email),
        "peer_display_name": (body.peer_display_name or "").strip() or None,
        "event_type": "watermark_trace",
        "trace_code": trace,
        "session_id": str(body.session_id or "").strip() or None,
        "user_agent": request.headers.get("user-agent"),
        "ip_address": _extract_ip(request),
        "created_at": now,
        "metadata": {
            "time_window_start": body.time_window_start,
            "time_window_end": body.time_window_end,
        },
    }

    try:
        saved = storage.create_audit_event(event)
    except Exception as exc:
        return {"ok": False, "error": f"watermark_trace_failed: {exc.__class__.__name__}"}

    return {"ok": True, "trace_code": saved.get("trace_code"), "created_at": saved.get("created_at")}


@router.get("/trace/{trace_code}")
def lookup_trace_event(trace_code: str):
    app_env = (os.getenv("APP_ENV") or "development").strip().lower()
    if app_env == "production":
        raise HTTPException(status_code=403, detail="trace_lookup_disabled_in_production")

    trace = str(trace_code or "").strip().upper()
    if not trace:
        raise HTTPException(status_code=400, detail="trace_code_required")

    event = storage.get_audit_event_by_trace_code(trace)
    if not event:
        raise HTTPException(status_code=404, detail="trace_code_not_found")
    return {"ok": True, "event": event}

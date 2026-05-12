from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Query

from app.services.storage_repository import StorageRepository

router = APIRouter(prefix="/api/notifications", tags=["notifications"])
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
storage = StorageRepository(data_dir=str(DATA_DIR))


def _norm(email: str) -> str:
    return email.strip().lower()


@router.get("")
def list_notifications(user: str = Query(...)):
    try:
        rows = storage.list_notifications(_norm(user))
        return {"ok": True, "notifications": rows}
    except Exception as exc:
        return {
            "ok": True,
            "notifications": [],
            "warning": f"list_notifications_failed: {exc.__class__.__name__}",
        }


@router.post("/{notif_id}/read")
def mark_read(notif_id: str):
    try:
        storage.mark_notification_read(notif_id)
    except Exception as exc:
        return {"ok": False, "error": f"mark_notification_read_failed: {exc.__class__.__name__}"}
    return {"ok": True}

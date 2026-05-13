from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from pathlib import Path
import os

from app.services.connection_service import ConnectionService

router = APIRouter(prefix="/api/connections", tags=["connections"])
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "profiles").mkdir(parents=True, exist_ok=True)
service = ConnectionService(
    connections_path=str(DATA_DIR / "connections.json"),
    accounts_path=str(DATA_DIR / "accounts.json"),
    profiles_dir=str(DATA_DIR / "profiles"),
)


class RequestConnectionBody(BaseModel):
    from_user: str
    to: str


class VerifyConnectionBody(BaseModel):
    connection_id: str
    user: str
    code: str


@router.post("/request")
def request_connection(req: RequestConnectionBody):
    try:
        return service.request_connection(from_user=req.from_user, to=req.to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/verify")
def verify_connection(req: VerifyConnectionBody):
    try:
        return service.verify_connection(
            connection_id=req.connection_id,
            user=req.user,
            code=req.code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/contacts")
def list_contacts(user: str = Query(..., description="user_id_or_email")):
    try:
        contacts = service.list_contacts(user=user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "contacts": contacts,
    }


@router.get("/status")
def connection_status(
    user: str = Query(..., description="current user email/user_id"),
    peer: str = Query(..., description="peer email/user_id"),
):
    try:
        return service.get_connection_status(user=user, peer=peer)
    except ValueError as exc:
        return {
            "ok": False,
            "reason": "peer_not_found",
            "error": str(exc),
        }

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

from app.api.conversation_api import router as conversation_router
from app.api.signature_api import router as signature_router
from app.api.auth_api import router as auth_router
from app.api.connection_api import router as connection_router
from app.api.chat_history_api import router as chat_history_router
from app.api.notification_api import router as notification_router
from app.api.audit_api import router as audit_router

app = FastAPI(title="CurveApp API")

frontend_origin_env = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
frontend_origins = [
    origin.strip()
    for origin in frontend_origin_env.split(",")
    if origin.strip()
]
if "http://localhost:3000" not in frontend_origins:
    frontend_origins.append("http://localhost:3000")
if "http://127.0.0.1:3000" not in frontend_origins:
    frontend_origins.append("http://127.0.0.1:3000")
if "https://curve-ed25519.vercel.app" not in frontend_origins:
    frontend_origins.append("https://curve-ed25519.vercel.app")

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_origin_regex=r"^https?://([a-zA-Z0-9-]+\.)?vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversation_router)
app.include_router(signature_router)
app.include_router(auth_router)
app.include_router(connection_router)
app.include_router(chat_history_router)
app.include_router(notification_router)
app.include_router(audit_router)

ws_clients: dict[str, WebSocket] = {}


def _ws_log(message: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[ws][{ts}] {message}")


@app.websocket("/ws")
async def websocket_compat(websocket: WebSocket):
    _ws_log("incoming websocket request /ws")
    await websocket.accept()
    _ws_log("websocket accepted /ws")
    client_id: str | None = None
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                packet = json.loads(raw)
            except Exception:
                _ws_log("ignored non-json websocket frame")
                continue
            packet_type = str(packet.get("packet_type") or "").lower()
            sender_id = str(packet.get("sender_id") or client_id or "").strip().lower()
            receiver_id = str(packet.get("receiver_id") or "").strip().lower()

            if packet_type == "connect":
                if sender_id:
                    client_id = sender_id
                    ws_clients[client_id] = websocket
                    _ws_log(f"client connected id={client_id}")
                    await websocket.send_text(
                        json.dumps(
                            {
                                "packet_id": f"hello-{int(datetime.now(timezone.utc).timestamp())}",
                                "packet_type": "system",
                                "sender_id": "server",
                                "receiver_id": client_id,
                                "created_at": datetime.now(timezone.utc).isoformat(),
                                "requires_ack": False,
                                "payload": {"status": "ok", "message": "ws connected"},
                            }
                        )
                    )
                continue

            if packet_type == "ping":
                await websocket.send_text(
                    json.dumps(
                        {
                            "packet_id": packet.get("packet_id"),
                            "packet_type": "pong",
                            "sender_id": "server",
                            "receiver_id": sender_id or client_id,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "requires_ack": False,
                            "payload": {},
                        }
                    )
                )
                continue

            if not sender_id:
                _ws_log("ignored packet without sender_id before connect")
                continue

            target = ws_clients.get(receiver_id)
            if target is not None:
                await target.send_text(json.dumps(packet))
    except WebSocketDisconnect:
        _ws_log(f"websocket disconnected id={client_id or '<unknown>'}")
    except Exception as exc:
        _ws_log(f"connection error id={client_id or '<unknown>'} error={exc}")
    finally:
        if client_id and ws_clients.get(client_id) is websocket:
            ws_clients.pop(client_id, None)
            _ws_log(f"client disconnected id={client_id}")


@app.get("/")
def health():
    return {"ok": True}



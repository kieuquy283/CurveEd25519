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

app = FastAPI(title="CurveApp API")

frontend_origin_env = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
frontend_origins = [
    origin.strip()
    for origin in frontend_origin_env.split(",")
    if origin.strip()
]
if "http://localhost:3000" not in frontend_origins:
    frontend_origins.append("http://localhost:3000")

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

ws_clients: dict[str, WebSocket] = {}


def _ws_log(message: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[ws][{ts}] {message}")


@app.websocket("/ws")
async def websocket_compat(websocket: WebSocket):
    await websocket.accept()
    client_id: str | None = None
    try:
        initial_raw = await websocket.receive_text()
        initial_packet = json.loads(initial_raw)
        if str(initial_packet.get("packet_type", "")).lower() != "connect":
            await websocket.close(code=1008, reason="First packet must be connect")
            return

        client_id = str(initial_packet.get("sender_id") or "").strip().lower()
        if not client_id:
            await websocket.close(code=1008, reason="Missing sender_id")
            return

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

        while True:
            raw = await websocket.receive_text()
            packet = json.loads(raw)
            packet_type = str(packet.get("packet_type") or "").lower()
            sender_id = str(packet.get("sender_id") or client_id).strip().lower()
            receiver_id = str(packet.get("receiver_id") or "").strip().lower()

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

            target = ws_clients.get(receiver_id)
            if target is not None:
                await target.send_text(json.dumps(packet))
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        _ws_log(f"connection error id={client_id or '<unknown>'} error={exc}")
    finally:
        if client_id and ws_clients.get(client_id) is websocket:
            ws_clients.pop(client_id, None)
            _ws_log(f"client disconnected id={client_id}")


@app.get("/")
def health():
    return {"ok": True}

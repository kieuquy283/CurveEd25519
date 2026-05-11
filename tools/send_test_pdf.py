import json
import base64
import urllib.request
import time

# Minimal PDF bytes
pdf_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 24 Tf 72 712 Td (Hi) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000010 00000 n \ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"

b64 = base64.b64encode(pdf_bytes).decode('ascii')

payload = {
    "sender": "alice",
    "recipient": "bob",
    "filename": "test.pdf",
    "mime_type": "application/pdf",
    "content_b64": b64,
}

data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request('http://127.0.0.1:8000/api/conversation/encrypt-file', data=data, headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req) as resp:
    body = resp.read().decode('utf-8')
    print(body)
    # Save envelope for websocket send
    try:
        resp_json = json.loads(body)
        envelope = resp_json.get("envelope")
    except Exception:
        envelope = None

import asyncio
import websockets

async def send_via_ws(envelope):
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        # send connect handshake as frontend does
        connect_pkt = {
            "packet_id": str(int(time.time()*1000)) + "-" + "connect",
            "packet_type": "connect",
            "sender_id": "alice",
            "receiver_id": "server",
            "created_at": "",
            "requires_ack": False,
            "encrypted": False,
            "payload": {"peer_id": "alice"}
        }
        await websocket.send(json.dumps(connect_pkt))

        # small pause
        await asyncio.sleep(0.2)

        if envelope:
            msg_pkt = {
                "packet_id": str(int(time.time()*1000)) + "-" + "msg",
                "packet_type": "message",
                "sender_id": "alice",
                "receiver_id": "frontend",
                "created_at": "",
                "requires_ack": True,
                "encrypted": True,
                "payload": {"envelope": envelope}
            }
            await websocket.send(json.dumps(msg_pkt))
            print("Sent message packet via websocket")

if envelope:
    asyncio.get_event_loop().run_until_complete(send_via_ws(envelope))

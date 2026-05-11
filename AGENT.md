# AGENT.md

## Project Context

This project is an end-to-end encrypted Curve25519 chat app.

Core crypto flow:
- X25519 for key agreement
- HKDF-SHA256 for key derivation
- ChaCha20-Poly1305 for AEAD encryption
- Ed25519 for signing/verifying message envelopes

Frontend:
- Next.js / React / TypeScript
- Chat UI under `ui/src/components`
- Stores under `ui/src/store`
- WebSocket service under `ui/src/services/websocket.ts`
- Crypto HTTP bridge under `ui/src/services/conversationCrypto.ts`

Backend:
- FastAPI app entry: `server.py`
- Conversation API: `app/api/conversation_api.py`
- Protocol orchestration: `app/services/protocol_service.py`
- Crypto orchestration: `app/services/crypto_service.py`
- Profiles stored in `data/profiles`

## Operating Rules

The agent may run terminal commands, install dependencies, start backend/frontend servers, inspect logs, and send test messages.

The agent must update `HANDOFF.md` after every completed task.

A task is only DONE when:
1. logic is implemented completely,
2. TypeScript/Python errors are fixed,
3. frontend compiles,
4. backend route works,
5. manual test path succeeds,
6. no visible console error remains for that feature.

Use PowerShell-compatible commands on Windows.

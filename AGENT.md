# AGENT.md — CurveEd25519 Secure Messenger Agent Guide

## Purpose

This repository is a Curve25519-family secure messenger. It combines a Python/FastAPI cryptographic backend with a Next.js/React/TypeScript frontend and a WebSocket transport layer.

Current engineering focus: restore and stabilize encrypted file sending in the chat UI after earlier frontend edits caused upload/send rendering to disappear. File messages must still expose encryption/decryption information in the UI.

## High-Level Architecture

### Backend

The backend owns cryptographic operations and profile/protocol orchestration.

Important areas:

- `server.py` — FastAPI/server entry point.
- `app/api/conversation_api.py` — HTTP bridge for conversation encryption/decryption APIs.
- `app/services/protocol_service.py` — high-level message/envelope orchestration.
- `app/services/crypto_service.py` — cryptographic operations.
- `data/profiles/` — local profile/key material storage.

Core crypto suite:

- `X25519` — key agreement.
- `HKDF-SHA256` — key derivation.
- `ChaCha20-Poly1305` — AEAD encryption.
- `Ed25519` — signing/verifying envelopes.

Do not replace this cryptographic design. Ed25519 is for signatures, not encryption.

### Frontend

The frontend is a Next.js/React/TypeScript chat application.

Important areas:

- `ui/src/components/` — UI components.
- `ui/src/components/MessageComposer.tsx` — message input, send button, and restored file picker logic.
- `ui/src/components/MessageBubble.tsx` or chat message rendering components — render text/file messages.
- `ui/src/components/attachments/` — attachment picker/preview/bubble components if present.
- `ui/src/components/crypto/` — crypto trace/visualization panels if present.
- `ui/src/providers/WebSocketProvider.tsx` — WebSocket packet routing into Zustand stores.
- `ui/src/services/websocket.ts` — WebSocket client service.
- `ui/src/services/conversationCrypto.ts` or equivalent — HTTP crypto bridge helpers, if present.
- `ui/src/store/useChatStore.ts` — conversation/message state.
- `ui/src/store/useAttachmentStore.ts` — attachment state, if present.
- `ui/src/types/models.ts` — domain model types.
- `ui/src/types/packets.ts` — transport packet types/builders.

State management uses Zustand. Keep global chat/attachment/typing/notification state in stores, not local-only component state unless it is composer-local UI state.

### Transport

Primary realtime transport is WebSocket.

Default endpoint:

```txt
ws://localhost:8765
```

Do not invent new REST transport for chat delivery. Existing HTTP crypto endpoints may be used for encryption/decryption only; realtime message delivery must continue through WebSocket packets.

Typical outgoing packet shape:

```ts
{
  packet_id: string,
  packet_type: PacketType.MESSAGE,
  sender_id: "frontend",
  receiver_id: conversationId,
  created_at: string,
  requires_ack: true,
  encrypted: true,
  payload: {
    envelope: encrypted.envelope
  }
}
```

## Message Flow

### Text message flow

1. User types text in `MessageComposer`.
2. Composer calls backend encrypt API, typically:
   - `POST /api/conversation/encrypt`
   - body: `{ sender, recipient, plaintext }`
3. Backend returns `{ ok, envelope, debug }`.
4. Frontend creates/updates optimistic message with crypto metadata.
5. Frontend sends WebSocket `PacketType.MESSAGE` carrying `payload.envelope`.
6. `WebSocketProvider` receives incoming packets and writes them into `useChatStore`.
7. UI renders the message bubble and crypto info if present.

### File message flow — current target

The current restored file path serializes file payload into encrypted plaintext JSON before calling the same encrypt endpoint.

`MessageComposer.tsx` should:

1. Let user select a local file.
2. Read file as base64 using `FileReader`.
3. Create JSON plaintext:

```json
{
  "type": "file",
  "text": "optional caption",
  "attachment": {
    "id": "uuid",
    "fileName": "example.pdf",
    "mimeType": "application/pdf",
    "size": 12345,
    "dataBase64": "...",
    "crypto": {
      "encrypted": true,
      "decrypted": true,
      "encryption": "ChaCha20-Poly1305",
      "keyExchange": "X25519",
      "kdf": "HKDF-SHA256",
      "signature": "Ed25519"
    }
  }
}
```

4. Encrypt this JSON plaintext via backend encrypt API.
5. Add an optimistic local message with `type: "file"`, attachment metadata, local data URL, and crypto fields.
6. Send only the encrypted envelope over WebSocket.

`WebSocketProvider.tsx` should:

1. Read `payload.envelope` from incoming `PacketType.MESSAGE`.
2. Use the decrypted plaintext if the current backend/provider path exposes it as `envelope.text` or another decrypted field.
3. If plaintext is JSON with `{ type: "file", attachment: ... }`, parse it and create:
   - `message.type = "file"`
   - `message.text = caption || "📎 filename"`
   - `message.file` and/or `message.attachments`
   - crypto metadata from `attachment.crypto`
4. If not JSON, preserve normal text handling.

If the backend decrypt endpoint is used for incoming envelopes in the existing code path, keep that route and parse the returned plaintext/message object into the same `ChatMessage` shape.

## Required UI Behavior for Files

For file messages, the UI must show:

- filename,
- mime type if useful,
- size,
- download/open link when local `data:` URL or decrypted content exists,
- encryption/decryption information:
  - `Mã hóa: ChaCha20-Poly1305`
  - `Trao đổi khóa: X25519`
  - `KDF: HKDF-SHA256`
  - `Chữ ký: Ed25519`
  - `Giải mã: Thành công` or a clear pending/unknown state.

Do not hide crypto information for file messages. This is a project requirement.

## Type Expectations

`ChatMessage` should support at least:

```ts
interface ChatMessage {
  id: string;
  packetId?: string;
  conversationId: string;
  from: string;
  to: string;
  text: string;
  timestamp: string;
  status: DeliveryState;
  type?: "text" | "file";
  file?: FileMessagePayload;
  attachments?: Attachment[];
  attachmentIds?: string[];
  envelope?: Record<string, unknown>;
  cryptoDirection?: "encrypt" | "decrypt";
  cryptoDebug?: Record<string, unknown> | null;
}
```

`Attachment` should support at least:

```ts
interface Attachment {
  id: string;
  fileName: string;
  mimeType: string;
  size: number;
  url?: string;
  localUrl?: string;
  uploaded: boolean;
  uploadProgress?: number;
  crypto?: {
    encrypted?: boolean;
    decrypted?: boolean;
    encryption?: string;
    keyExchange?: string;
    kdf?: string;
    signature?: string;
  };
  envelope?: Record<string, unknown>;
  debug?: Record<string, unknown> | null;
}
```

Adapt names if the current codebase already uses `filename`, `mime_type`, or `content_b64`; keep compatibility by mapping both snake_case and camelCase.

## Current Active Repair Sequence

The user has already been given a replacement `MessageComposer.tsx` that:

- restores a file picker button,
- reads selected file to base64,
- sends JSON file payload through the existing encrypt API,
- creates an optimistic file message,
- stores crypto metadata on the optimistic attachment,
- fixes TypeScript nullability by snapshotting `const file = pendingFile` inside `handleSend`.

Next files to inspect/fix in order:

1. `ui/src/providers/WebSocketProvider.tsx`
   - Parse incoming decrypted file JSON.
   - Attach `attachments`/`file` to `ChatMessage`.
   - Preserve ACK, typing, presence, notification behavior.

2. `ui/src/types/models.ts`
   - Add missing `type`, `file`, `attachments`, `cryptoDebug`, `envelope`, `cryptoDirection`, and `Attachment.crypto` fields if TypeScript complains.

3. `ui/src/components/MessageBubble.tsx` or equivalent message renderer
   - Render file attachments/messages.
   - Keep text message behavior unchanged.

4. `ui/src/components/attachments/AttachmentPreview.tsx`, `AttachmentBubble.tsx`, or equivalent
   - Show file info.
   - Show crypto/decrypt info for files.
   - Provide clickable open/download behavior where possible.

5. `ui/src/store/useAttachmentStore.ts` if the app uses attachment IDs rather than embedding attachments on messages.
   - Store/retrieve attachment metadata, local data URLs, envelope/debug/crypto fields.

## Operating Rules for Agents

### Never

- Do not rewrite backend architecture.
- Do not replace WebSocket transport with REST chat delivery.
- Do not change packet schema unless absolutely necessary and backward-compatible.
- Do not remove typing/presence/notification/ACK behavior while fixing files.
- Do not disable TypeScript strictness.
- Do not hide build errors.
- Do not remove crypto metadata from file messages.

### Always

- Prefer small targeted patches.
- Preserve existing stores and component boundaries.
- Keep text messaging working while restoring file sending.
- Run frontend build after changes:

```powershell
cd ui
npm run build
```

- If backend is touched, restart/test backend and verify the relevant endpoint.
- Update `HANDOFF.md` after every completed task.
- Record modified files and validation results.

## Manual Test Path

Use this path before marking the task done:

1. Start backend/API server.
2. Start WebSocket transport server if separate.
3. Start frontend.
4. Open a conversation.
5. Send a normal text message.
   - Optimistic message appears.
   - Message reaches WebSocket path.
   - ACK/delivery state works.
6. Select a file from the composer.
   - File preview appears before sending.
   - Crypto info appears in preview.
7. Send the file.
   - File message appears optimistically.
   - WebSocket packet is sent.
   - Receiver/incoming path renders file bubble.
   - Filename/size/open-download and crypto/decrypt info are visible.
8. Run `npm run build` in `ui`.
9. Confirm no visible browser console errors for the touched feature.

## Notes for Codex/Autonomous Agents

- The repository may contain older documentation that says attachment transport is incomplete. Treat this new `AGENT.md` and `HANDOFF.md` as the latest execution state.
- Some prior frontend versions used an `AttachmentPicker` component; recent repair moved upload logic directly into `MessageComposer.tsx`. Do not blindly duplicate both paths. Inspect current code first.
- If both `attachments` and `file` fields exist, render either one. Prefer `attachments` for multi-file extensibility but keep `file` for compatibility.
- If incoming packets contain only encrypted envelopes and not decrypted plaintext, wire the provider through the existing decrypt API before parsing file JSON.

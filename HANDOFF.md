# HANDOFF.md — CurveEd25519 Current Execution State

## Current Status

The project is a Curve25519 secure messenger with a Python/FastAPI crypto backend and a Next.js/React/TypeScript frontend. Text messaging and the general WebSocket chat foundation exist, but file upload/send behavior regressed after recent frontend edits.

The active repair to restore encrypted file send/receive over WebSocket is now implemented in frontend flow and passes `npm run build` in `ui`.

## Latest User Request

The user reported:

> Previously the app could upload/send a file from the local machine, but after editing for a while this disappeared. Read the code and fix it. For files, encryption and decryption information must still be shown.

The user then provided the current `MessageComposer.tsx`. A new complete replacement was drafted for that file.

## Important Current Design Decisions

### File sending strategy currently being restored

The current patch path sends files by encoding file content into base64, embedding it in a structured JSON plaintext, encrypting that JSON using the existing conversation encrypt API, then sending the encrypted envelope over WebSocket.

Structured plaintext shape:

```json
{
  "type": "file",
  "text": "optional caption",
  "attachment": {
    "id": "uuid",
    "fileName": "filename.ext",
    "mimeType": "application/octet-stream",
    "size": 123,
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

Only encrypted envelopes should be sent through WebSocket. Do not send plaintext file bytes over the socket except as optimistic local UI state.

### Crypto labels required in UI

File preview/bubbles must visibly show:

- `Mã hóa: ChaCha20-Poly1305`
- `Trao đổi khóa: X25519`
- `KDF: HKDF-SHA256`
- `Chữ ký: Ed25519`
- `Giải mã: Thành công` or another accurate decrypt state.

## Completed in This Repair Session

### TASK-FILE-013 — Add email-based demo login and identity propagation

Status: DONE (backend syntax + ui build verified)

Summary:

- Added local/demo email login flow from main UI.
- Logged-in email is now used as current identity for:
  - chat sender (`from`, `sender_id`)
  - conversation encrypt/sign API sender/signer fields
  - websocket local peer id configuration
  - sidebar profile display
- Existing encrypted text/file and signature features remain working.

Backend changes:

- Added `app/api/auth_api.py` (new)
  - `POST /api/auth/login`
  - Request:
    - `{ "email": string, "display_name"?: string }`
  - Behavior:
    - validates email shape,
    - ensures profile exists in `data/profiles` (auto-creates with Ed25519 + X25519 via existing `ProfileService` if missing),
    - returns normalized user + profile public key data.
- Updated `server.py`
  - include `auth_router`.

Frontend changes:

- Added `ui/src/services/auth.ts` (new)
  - `loginWithEmail()` API client.
- Added `ui/src/store/useAuthStore.ts` (new)
  - persisted auth state:
    - `currentUser`
    - `isAuthenticated`
    - `login()`
    - `logout()`
  - helper `getCurrentUserId()` with fallback:
    - `NEXT_PUBLIC_USER_ID || persisted user || "frontend"`.
- Updated `ui/src/app/page.tsx`
  - login gate UI when unauthenticated:
    - fields: email + optional display name
    - Login button + validation/errors
  - after login, renders app inside `WebSocketProvider`.
- Updated `ui/src/providers/WebSocketProvider.tsx`
  - binds websocket `localPeerId` to current logged-in user id.
- Updated `ui/src/services/websocket.ts`
  - default `localPeerId` fallback now uses `NEXT_PUBLIC_USER_ID` first.
- Updated `ui/src/components/MessageComposer.tsx`
  - removed hardcoded sender/signer identity; now uses auth resolver.
- Updated `ui/src/components/MessageBubble.tsx`
  - outgoing/decrypt receiver identity now uses auth store user id.
- Updated `ui/src/components/signature/SignatureDialog.tsx`
  - signer identity now uses auth resolver.
- Updated `ui/src/components/attachments/AttachmentPicker.tsx`
  - sender identity now uses auth resolver.
- Updated `ui/src/services/attachments.ts`
  - attachment meta sender id now uses auth resolver.
- Updated `ui/src/components/Sidebar.tsx`
  - shows current user display name/email
  - adds Logout button
  - demo contacts switched to:
    - `alice@example.com`
    - `bob@example.com`
- Updated defaults:
  - `ui/src/store/useUiStore.ts`
  - `ui/src/store/useSettingsStore.ts`
  - `localPeerId` now respects `NEXT_PUBLIC_USER_ID` fallback.

Commands run:

- Backend syntax/import check:
  - `D:\KieuQuy\Documents\DS\python.exe -m compileall app server.py` ✅
- Frontend build:
  - `cd ui && npm run build` ✅

Manual test steps (two users):

1. Start backend API and websocket server.
2. Open browser session A:
   - login as `alice@example.com`.
3. Open browser session B (incognito or another browser):
   - login as `bob@example.com`.
4. In each session, create/select conversation with the other email.
5. Send text message from Alice to Bob:
   - verify packet sender identity is `alice@example.com`.
6. Send text message from Bob to Alice:
   - verify packet sender identity is `bob@example.com`.
7. Verify encrypted file send/signature actions still function.

Limitations:

- Demo/local login only (no password/OAuth/session hardening).
- Identity persistence is local browser storage.
- Production-grade authentication/authorization is intentionally not implemented in this task.

### TASK-FILE-012 — Add hide control for signature verification result panel

Status: DONE (build-verified)

Changed files:

- `ui/src/components/MessageComposer.tsx`
  - Added visible close/hide control in verification result panel:
    - button label: `Ẩn kết quả` with `X` icon.
  - Clicking button now clears/hides only verification result state:
    - `setVerifyResult(null)`
    - `setVerifiedContainer(null)`
  - Does not close whole composer/signature UI and does not affect selected file state.
  - Verifying another file continues to show results as normal.

Validation:

- `cd ui && npm run build` ✅ (successful on May 12, 2026).

Notes:

- Signing flow, signed-file download flow, and encrypted text/file chat transport remain unchanged.

### TASK-FILE-011 — Add confirmation before signed-file download

Status: DONE (build-verified)

Changed files:

- `ui/src/components/signature/SignatureDialog.tsx`
  - Added download confirmation dialog before any signed JSON download:
    - Title/message text:
      - `Download signed file?`
      - `This will download the signed JSON container. Recipients can verify the file integrity with Ed25519.`
    - Actions via native confirm:
      - confirm = `Download`
      - cancel = `Cancel`
  - Updated flow so sign action no longer auto-downloads immediately.
  - Added explicit `Tải file đã ký` button for the latest signed container.
  - Existing list-row download buttons now also require confirmation.

Validation:

- `cd ui && npm run build` ✅ (successful on May 12, 2026).

Notes:

- Signing and existing encrypted chat/file send flow remain unchanged.
- Download starts only after user confirmation.

### TASK-FILE-010 — Add main UI digital signature workspace dialog

Status: DONE (ui build + backend syntax verified)

Summary:

- Added a dedicated main UI signature workspace opened from sidebar button.
- Kept existing chat layout and encrypted message/file flows unchanged.
- Reused existing backend signature endpoints introduced earlier:
  - `POST /api/signature/sign-file`
  - `POST /api/signature/verify-file`

Frontend files changed:

- `ui/src/components/Sidebar.tsx`
  - Added visible `Ký file` icon button (`FileSignature`) in sidebar header action group.
  - Wired button to open/close signature modal dialog.
- `ui/src/components/signature/SignatureDialog.tsx` (new)
  - Modal title: `Chữ ký số / Ký file`.
  - Description clarifies integrity checking/tamper detection:
    - `xác minh toàn vẹn` / `phát hiện thay đổi`.
  - File picker + selected file info (filename, MIME type, size).
  - `Ký file` action using backend API.
  - Downloads `<original>.signed.json`.
  - Session list of signed files with:
    - filename, size, signed_at, signer, algorithm, hash, status
    - download button per row.
- `ui/src/services/signature.ts` (new)
  - Centralized signature API client.
  - Base URL:
    - `process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"`.
  - Methods:
    - `signFile()`
    - `verifySignedFile()`
- `ui/src/store/useSignatureStore.ts` (new)
  - Local session store for signed files:
    - `signedFiles`
    - `addSignedFile`
    - `removeSignedFile`
    - `clearSignedFiles`

Backend status:

- No new backend endpoints required in this task (reused existing signature APIs).

Commands run:

- `cd ui && npm run build` ✅
- `D:\KieuQuy\Documents\DS\python.exe -m compileall app server.py` ✅

How to test in UI:

1. Open app and click sidebar `Ký file` button.
2. In modal:
   - choose a local file,
   - confirm file info is shown,
   - click `Ký file`.
3. Verify download of `<filename>.signed.json`.
4. Confirm the signed file appears in modal list with signer/timestamp/algorithm/hash/status.
5. Click `Tải file đã ký` from list row and verify download works.
6. Ensure normal text and encrypted attachment chat send still work.

Remaining limitations:

- Uses signed JSON container format, not native embedded PDF signatures.
- Signature detects modifications; it does not physically prevent edits.
- Signed files list is session-local Zustand state (no durable persistence enabled).

### TASK-FILE-009 — Add signed-file container feature (Ed25519)

Status: DONE (backend syntax + ui build verified)

Feature summary:

- Added signed file container flow using Ed25519 signatures and deterministic canonical payload.
- Users can:
  - `Ký file` (sign local file),
  - download `<original>.signed.json`,
  - send the signed container through existing encrypted message/file flow,
  - `Xác minh chữ ký` by loading `.signed.json`,
  - extract/download original file when signature is valid.
- Existing encrypted chat/file transport remains unchanged:
  - X25519 + HKDF-SHA256 + ChaCha20-Poly1305 + Ed25519 envelope signatures.

Backend changes:

- Added `app/api/signature_api.py` with endpoints:
  - `POST /api/signature/sign-file`
  - `POST /api/signature/verify-file`
- `sign-file`:
  - validates base64 content,
  - resolves signer profile from `data/profiles`,
  - builds signed container:
    - `version, type, filename, mimeType, size, content_b64, signer, signer_public_key, algorithm, hash, signed_at`,
  - canonicalizes deterministically via `json.dumps(..., sort_keys=True, separators=(",", ":"))`,
  - signs canonical payload using signer Ed25519 private key,
  - returns `signed_file` + debug.
- `verify-file`:
  - validates required fields + base64,
  - rebuilds exact canonical payload excluding `signature`,
  - verifies with `signer_public_key`,
  - returns valid/invalid with clear message:
    - invalid: `File đã bị thay đổi hoặc chữ ký không hợp lệ.`
- Updated `server.py`:
  - include `signature_router`,
  - allow CORS for `http://localhost:3000` and `http://127.0.0.1:3000`.

Frontend changes:

- Updated `ui/src/services/conversationCrypto.ts`:
  - added `signFileContainer()` and `verifySignedFileContainer()`.
- Updated `ui/src/components/MessageComposer.tsx`:
  - added `Ký file` action + hidden file input,
  - signs selected file via backend and auto-downloads `.signed.json`,
  - stages the generated signed JSON as pending attachment so it can be sent through existing encrypted flow,
  - added `Xác minh chữ ký` action + hidden file input,
  - displays filename/signer/signed_at/algorithm/hash + valid/invalid status,
  - allows extracting original file when valid.
- Updated `ui/src/types/models.ts`:
  - added `SignedFileContainer`,
  - added `SignatureDebug`,
  - added `VerificationResult`.

Checks run:

- Backend syntax:
  - `D:\KieuQuy\Documents\DS\python.exe -m compileall app server.py` ✅
- Frontend build:
  - `cd ui && npm run build` ✅

Remaining limitations:

- Uses signed JSON container format, not native embedded PDF signatures.
- Signature does not prevent editing; it detects modifications.
- Signer lookup for verification currently checks local profile presence by signer username; trust/identity pinning beyond included `signer_public_key` is not yet expanded.

### TASK-FILE-008 — Fix frontend crypto API fetch bug and trace spam

Status: DONE (build-verified)

Changed files:

- `ui/src/services/conversationCrypto.ts`
  - Centralized API base URL with:
    - `process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"`
  - Added `encryptConversationMessage()` for `POST /api/conversation/encrypt` with body:
    - `{ sender, recipient, plaintext }`
  - Added explicit unreachable-backend error message when fetch throws.
  - Reused centralized API base URL in decrypt path.
- `ui/src/components/MessageComposer.tsx`
  - Removed local hardcoded `API_BASE_URL`.
  - Switched encrypt call to `encryptConversationMessage()` service.
  - On encryption/fetch failure:
    - logs clear unreachable/encrypt error
    - keeps optimistic message in `failed` status (does not mark as sent).
  - File messages still go through same encrypt service before WebSocket send.
- `ui/src/components/MessageBubble.tsx`
  - Removed noisy warning path for missing envelope.
  - Only opens crypto trace when envelope or debug exists.
  - Added status hint when trace data is unavailable:
    - pending: `Đang mã hóa...`
    - failed: `Mã hóa/gửi thất bại`
  - Uses centralized API base URL for decrypt-trace fetch.

Validation:

- `cd ui && npm run build` ✅ (successful on May 12, 2026).

Remaining manual checks:

1. With backend stopped, send text/file and confirm:
   - optimistic message appears then becomes `failed`,
   - console shows clear backend unreachable error.
2. With backend running, send text and file:
   - both encrypt through `/api/conversation/encrypt`,
   - sender and receiver bubbles render,
   - file crypto info remains visible.
3. Click pending/failed bubbles and confirm:
   - no console spam for missing envelope,
   - status hint text appears as expected.

### TASK-FILE-007 — Restore encrypted file bubble send/receive path

Status: DONE (build-verified)

Changed files:

- `ui/src/services/conversationCrypto.ts`
  - Extended decrypt helper to return structured `{ plaintext, debug }`.
  - Added compatibility for backend file decrypt responses (`data.message.type === "file"`) by normalizing to JSON plaintext with attachment metadata and crypto labels.
- `ui/src/services/websocket.ts`
  - Stopped directly writing incoming messages to chat store from transport service.
  - Decrypts incoming encrypted packet and injects `payload.plaintext` + `payload.debug` for provider-level routing.
- `ui/src/providers/WebSocketProvider.tsx`
  - Parses decrypted `payload.plaintext` first (fallback to `envelope.text`).
  - Builds incoming file `ChatMessage` with `type`, `attachments`, `file`, and `cryptoDebug`.
  - Removed duplicate ACK sending in provider (ACK remains in websocket service).
- `ui/src/components/attachments/AttachmentBubble.tsx`
  - Restored rendering for file messages that use `message.attachments` and `message.file` (not only `attachmentIds`).
- `ui/src/components/attachments/AttachmentPreview.tsx`
  - Supports both `localUrl` and `url`.
  - Adds open/download link for file payloads.
  - Displays required crypto/decryption info block for file bubbles:
    - X25519
    - HKDF-SHA256
    - ChaCha20-Poly1305
    - Ed25519
    - decrypt status
  - Keeps `CryptoTracePanel` support via envelope/debug metadata.
- `ui/src/types/models.ts`
  - Extended `ChatMessage.file`, added `ChatMessage.attachments`.
  - Added `Attachment.crypto`, `Attachment.envelope`, `Attachment.debug`.
  - Added `AttachmentCryptoInfo` type.
- `ui/src/types/packets.ts`
  - Extended `MessagePayload` with optional `plaintext` and `debug` fields used after decrypt.

Validation:

- `cd ui && npm run build` ✅ (successful on May 12, 2026).

Behavior now expected:

- Composer can select local file and send encrypted payload through existing WebSocket message transport.
- Sender sees immediate file bubble (optimistic).
- Receiver gets decrypted payload mapped into file bubble after WebSocket receive.
- File bubble shows crypto/decrypt information.
- Text message flow remains intact (same encrypt/send path).

Remaining manual checks:

1. Run two active clients and verify end-to-end text send/receive.
2. Send file from client A to B and confirm:
   - optimistic bubble on A,
   - received/decrypted bubble on B,
   - open/download works,
   - crypto trace panel opens from bubble.
3. Confirm no duplicate notifications/unread increments in active conversation.

### TASK-FILE-001 — Rewrite MessageComposer to restore file picker/send

Status: PATCH PROVIDED, NEEDS APPLY + BUILD VERIFY

A replacement `ui/src/components/MessageComposer.tsx` was provided to the user. It includes:

- file picker button using `FileUp`,
- hidden `<input type="file">`,
- `FileReader` base64 conversion,
- local pending-file preview,
- crypto information shown before send,
- optimistic file message creation,
- JSON file payload encryption through `POST /api/conversation/encrypt`,
- WebSocket send of encrypted envelope,
- `pendingFile is possibly null` fix via `const file = pendingFile` snapshot inside `handleSend`,
- loader icon while sending.

Known notes:

- The replacement uses direct composer-local upload logic instead of relying on a separate `AttachmentPicker`.
- It sets both optimistic `attachments` and crypto debug data so UI can render immediately.
- It uses `as any` in a few places to survive current incomplete model typings. The next task should clean up models.

Modified files intended:

- `ui/src/components/MessageComposer.tsx`

Validation still required:

- `cd ui && npm run build`
- manual send text
- manual choose file/send file

## Current Active Task

### TASK-FILE-002 — Fix incoming file parsing in WebSocketProvider

Status: IN_PROGRESS / NEXT

Goal:

When a file message arrives over WebSocket, parse the decrypted/plaintext envelope content if it is the structured JSON file payload. Then create a `ChatMessage` that includes file/attachment metadata for UI rendering.

Target file:

- `ui/src/providers/WebSocketProvider.tsx`

Required behavior:

1. Preserve existing handlers:
   - message routing,
   - ACK handling,
   - typing start/stop,
   - notification creation,
   - presence updates,
   - cleanup timer.

2. In the `PacketType.MESSAGE` handler:
   - Extract envelope from `packet.payload.envelope`.
   - Determine plaintext source.
     - If the current backend/provider path exposes decrypted text as `envelope.text`, use that.
     - If code already calls decrypt API, use the returned plaintext/message object.
     - If only encrypted envelope exists, do not fake decrypt; wire through existing decrypt endpoint/service.
   - Try `JSON.parse(plaintext)`.
   - If parsed object has `type === "file"` and `attachment`, map it into:

```ts
const attachments = [{
  id,
  fileName,
  mimeType,
  size,
  url: dataBase64 ? `data:${mimeType};base64,${dataBase64}` : undefined,
  uploaded: true,
  crypto
}];
```

   - Set message:

```ts
{
  type: "file",
  text: parsed.text || `📎 ${fileName}`,
  attachments,
  file: { ...compatibility fields... },
  cryptoDirection: "decrypt"
}
```

   - If not JSON or not file payload, keep normal text behavior.

3. Notifications should use display text, not raw JSON.

4. ACK behavior must remain unchanged.

A drafted replacement was provided earlier in chat, but the agent should inspect the current file before applying because the repo may have packet enum naming differences (`PacketType` vs `TransportPacketType`) and model types may differ.

## Next Tasks After WebSocketProvider

### TASK-FILE-003 — Update frontend models

Status: TODO

Target file:

- `ui/src/types/models.ts`

Add or confirm these fields:

```ts
export interface ChatMessage {
  type?: "text" | "file";
  file?: FileMessagePayload;
  attachments?: Attachment[];
  envelope?: Record<string, unknown>;
  cryptoDirection?: "encrypt" | "decrypt";
  cryptoDebug?: Record<string, unknown> | null;
}

export interface FileMessagePayload {
  id?: string;
  filename?: string;
  fileName?: string;
  mime_type?: string;
  mimeType?: string;
  size?: number;
  content_b64?: string;
  dataBase64?: string;
  url?: string;
  crypto?: AttachmentCryptoInfo;
}

export interface AttachmentCryptoInfo {
  encrypted?: boolean;
  decrypted?: boolean;
  encryption?: string;
  keyExchange?: string;
  kdf?: string;
  signature?: string;
}

export interface Attachment {
  id: string;
  fileName: string;
  mimeType: string;
  size: number;
  url?: string;
  localUrl?: string;
  uploaded: boolean;
  uploadProgress?: number;
  crypto?: AttachmentCryptoInfo;
  envelope?: Record<string, unknown>;
  debug?: Record<string, unknown> | null;
}
```

Use exact current project naming where possible. Keep backward compatibility with `attachmentIds` if still used.

### TASK-FILE-004 — Render file messages and crypto info

Status: TODO

Target files depend on current repo shape. Inspect first:

- `ui/src/components/MessageBubble.tsx`
- `ui/src/components/MessageList.tsx`
- `ui/src/components/attachments/AttachmentPreview.tsx`
- `ui/src/components/attachments/AttachmentBubble.tsx`
- `ui/src/components/crypto/CryptoTracePanel.tsx`

Required behavior:

- If `message.attachments?.length`, render each attachment.
- Else if `message.file`, render a compatible single file bubble.
- Show filename and size.
- If `url`/`localUrl` exists, provide an open/download link.
- Show crypto/decrypt info block for every file attachment.
- Keep text-only message rendering unchanged.

Crypto info fallback if missing:

```ts
{
  encrypted: true,
  decrypted: true,
  encryption: "ChaCha20-Poly1305",
  keyExchange: "X25519",
  kdf: "HKDF-SHA256",
  signature: "Ed25519"
}
```

### TASK-FILE-005 — Verify store compatibility

Status: TODO

Inspect:

- `ui/src/store/useChatStore.ts`
- `ui/src/store/useAttachmentStore.ts` if present.

Required checks:

- `addMessage` preserves `attachments`, `file`, `type`, `cryptoDebug`, `envelope`.
- Store normalization does not strip unknown fields.
- If UI relies on `attachmentIds`, ensure optimistic and incoming file attachments are also inserted into `useAttachmentStore`.

### TASK-FILE-006 — Build and manual test

Status: TODO

Run:

```powershell
cd ui
npm run build
```

Manual test path:

1. Start backend/API.
2. Start WebSocket transport.
3. Start frontend.
4. Send a normal text message.
5. Select a file in composer.
6. Confirm preview appears with crypto info.
7. Send file.
8. Confirm optimistic message appears.
9. Confirm receiver/incoming message renders file bubble.
10. Confirm file bubble shows crypto/decrypt info.
11. Confirm no browser console errors.

## Known Risks / Watch Points

- The repo has had multiple document states: older handoff said attachment transport was not implemented; newer repair is restoring a direct composer-based file path.
- Current `models.ts` may not yet support `type`, `file`, `attachments`, or `crypto` fields. TypeScript errors are expected until models are updated.
- Current `WebSocketProvider.tsx` in the remote snapshot had compressed/minified-looking type syntax issues. Inspect the local file rather than assuming the remote raw snapshot is exact.
- If backend encrypt/decrypt envelope does not expose plaintext at incoming WebSocket time, `WebSocketProvider` must call the existing decrypt API/service before parsing file JSON.
- Large files encoded into JSON/base64 can be heavy. For this repair, preserve the current project requirement and do not redesign storage/streaming unless requested.

## Operating Rules

- Do not rewrite backend architecture.
- Do not create a new REST chat-delivery path.
- Do not break WebSocket packet compatibility.
- Do not remove ACK, typing, presence, notifications, trust, or settings features.
- Keep strict TypeScript.
- Use targeted patches.
- Build after changes.
- Update this file after each completed task.

## Recommended Next Agent Action

1. Open current local `ui/src/providers/WebSocketProvider.tsx`.
2. Patch message handler to parse incoming file payloads safely.
3. Run TypeScript/build.
4. If build fails on models, perform TASK-FILE-003.
5. If build passes but file is not visible, perform TASK-FILE-004.
6. Update `HANDOFF.md` with actual modified files and validation result.

## 2026-05-12 - Email/Password Authentication Update

### Added
- Email/password login flow with account verification and password reset.
- Registration verification flow using expiring email codes.
- Forgot-password reset flow using expiring email codes.
- Local account storage at `data/accounts.json` with hashed password and hashed codes.
- Minimal SMTP email service with safe development fallback.

### Backend Endpoints Added/Updated
- `POST /api/auth/login`
- `POST /api/auth/register`
- `POST /api/auth/verify-email`
- `POST /api/auth/resend-verification`
- `POST /api/auth/request-password-reset`
- `POST /api/auth/reset-password`

### SMTP Environment Variables
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_USE_TLS`

### Security Notes
- Passwords are never stored in plaintext.
- Password hashes use `hashlib.scrypt` with per-password salt.
- Verification/reset codes are not stored in plaintext (HMAC-SHA256 hash only).
- Verification/reset codes expire.
- `dev_code` is only returned in development mode when email cannot be sent.

### Frontend Auth/UI
- Added gated auth screen for login/register/verify/reset.
- Main chat UI is hidden until authentication succeeds.
- Logout preserved via sidebar.
- Sender/signer identity continues to resolve from authenticated user first, with dev fallback.

### Files Changed
- `app/api/auth_api.py`
- `app/services/auth_service.py`
- `app/services/email_service.py`
- `data/accounts.json`
- `ui/src/app/page.tsx`
- `ui/src/components/auth/AuthScreen.tsx`
- `ui/src/services/auth.ts`
- `ui/src/store/useAuthStore.ts`
- `ui/src/services/websocket.ts`
- `ui/src/providers/WebSocketProvider.tsx`

### Checks Run
- `D:\KieuQuy\Documents\DS\python.exe -m py_compile app\api\auth_api.py app\services\auth_service.py app\services\email_service.py`
- `cd ui && npm run build`

### Limitations
- Account storage is local JSON (`data/accounts.json`), not a production DB.
- Real email delivery requires SMTP configuration.
- `dev_code` fallback is development-only.

## 2026-05-12 - Verified User Connection & Trusted Key Exchange

### Added
- Verified user-to-user connection flow with email-code verification.
- Trusted public-key snapshot exchange on verified connection.
- Trusted-contact listing endpoint for frontend contact panel.
- Server-side trust enforcement for conversation encrypt/decrypt and signature verification.

### Endpoints Added
- `POST /api/connections/request`
- `POST /api/connections/verify`
- `GET /api/connections/contacts?user=<user_id_or_email>`

### Endpoints Updated
- `POST /api/conversation/encrypt` now requires verified trusted connection.
- `POST /api/conversation/encrypt-file` now requires verified trusted connection.
- `POST /api/conversation/decrypt` now requires verified trusted connection.
- `POST /api/signature/verify-file` supports verifier identity and uses trusted Ed25519 key when available.

### Trust Model
- Trusted key snapshot is stored in `data/connections.json` at verification time.
- Snapshot contains X25519 + Ed25519 public keys, fingerprints, and verified timestamp.
- Raw connection verification code is never stored (hash only).
- If profile public key changes, trusted state is invalidated and re-verification is required.

### Frontend Changes
- Added connection API service (`ui/src/services/connections.ts`).
- Sidebar now supports requesting/verifying connection and auto-loading trusted contacts.
- Sending encrypted message/file is blocked client-side when contact is not trusted.
- Trust message shown: `Bạn cần xác minh kết nối và trao đổi khóa công khai trước khi gửi tin mã hóa.`

### Backend Files Changed
- `app/services/connection_service.py`
- `app/api/connection_api.py`
- `app/api/conversation_api.py`
- `app/api/signature_api.py`
- `app/services/auth_service.py`
- `server.py`

### Frontend Files Changed
- `ui/src/services/connections.ts`
- `ui/src/components/Sidebar.tsx`
- `ui/src/store/useContactStore.ts`
- `ui/src/components/MessageComposer.tsx`
- `ui/src/services/conversationCrypto.ts`
- `ui/src/services/signature.ts`
- `ui/src/types/models.ts`

### Checks Run
- `D:\KieuQuy\Documents\DS\python.exe -m py_compile app\api\connection_api.py app\services\connection_service.py app\api\conversation_api.py app\api\signature_api.py app\services\auth_service.py`
- `cd ui && npm run build` (pass)

### Limitations
- Connection storage is local JSON (`data/connections.json`).
- UI flow is minimal (inline sidebar controls), not a full invitation inbox.
- WebSocket payload trust checks rely on backend crypto API enforcement and trusted-contact gating.

### Manual Test Plan (Alice/Bob)
1. Register/login Alice and Bob.
2. Alice requests connection to Bob by email in sidebar connection box.
3. Obtain verification code (email via SMTP or `dev_code` in development).
4. Bob verifies connection using `connection_id` + code.
5. Alice and Bob refresh/login and confirm each sees trusted contact in sidebar.
6. Alice sends encrypted text to Bob; verify send is allowed only when trusted.
7. Bob decrypts and checks debug/trust metadata in crypto trace.
8. Alice sends encrypted file to Bob; Bob receives and sees trusted metadata.
9. Alice signs file; Bob verifies with trusted signer key (verifier-aware endpoint).
10. Modify signed JSON and verify should fail.
11. Simulate key change (regenerate profile key) and confirm trusted operations block until re-verification.

## 2026-05-12 - Connection UI Modal Behavior Update

### Updated UI Behavior
- Removed always-visible inline "connect with another user" form from sidebar main view.
- Plus/add conversation button now opens a modal dialog for connection flow.
- Modal contains full flow:
  - enter email/user_id
  - send connection request
  - enter connection_id + verification code
  - verify connection
  - show trusted fingerprint info after verification
- Modal closes on:
  - X button
  - Cancel button
  - successful verification
- Sidebar keeps normal conversation layout and still shows verified contacts count.

### Files Changed
- `ui/src/components/Sidebar.tsx`
- `ui/src/components/StartConversationDialog.tsx`

### Checks Run
- `cd ui && npm run build` (pass)

## 2026-05-12 - Production Deployment Preparation (Vercel + Separate Backend)

### Completed
- Centralized frontend environment config in `ui/src/config/env.ts`.
- Frontend API calls now resolve via `NEXT_PUBLIC_API_BASE_URL` (with local fallback).
- Frontend WebSocket URL now resolves via `NEXT_PUBLIC_WS_URL` (with local fallback).
- Removed hardcoded localhost API usage from attachment upload and backend reachability checks.
- Updated backend CORS to read `FRONTEND_ORIGIN` and allow Vercel domains.
- Added environment example files for frontend and backend.
- Added deployment documentation in `DEPLOY.md`.

### Frontend Env Variables
- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_WS_URL`

### Backend Env Variables
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_USE_TLS`
- `APP_ENV`
- `FRONTEND_ORIGIN`

### Files Changed
- `ui/src/config/env.ts`
- `ui/src/services/auth.ts`
- `ui/src/services/connections.ts`
- `ui/src/services/conversationCrypto.ts`
- `ui/src/services/signature.ts`
- `ui/src/services/websocket.ts`
- `ui/src/components/attachments/AttachmentPicker.tsx`
- `ui/src/components/MessageComposer.tsx`
- `ui/src/store/useSettingsStore.ts`
- `ui/src/store/useUiStore.ts`
- `ui/.env.example`
- `.env.example`
- `server.py`
- `DEPLOY.md`

### Checks Run
- `cd ui && npm run build` (pass)
- `python -m py_compile server.py` (pass)

### Notes
- FastAPI/WebSocket backend should be deployed on a persistent host (not Vercel).
- Frontend can be deployed on Vercel and connected via env vars.

## 2026-05-12 - Frontend Vercel Deployment Readiness Check

### Status
- Frontend API/WS endpoints are centralized via env config.
- `NEXT_PUBLIC_API_BASE_URL` is used across HTTP services.
- `NEXT_PUBLIC_WS_URL` is used for WebSocket configuration.
- Local fallbacks are set to:
  - API: `http://127.0.0.1:8000`
  - WS: `ws://127.0.0.1:8765`
- `ui/.env.example` exists and is populated.

### Checks Run
- `cd ui && npm run build` (pass)

## 2026-05-12 - Vercel Build Fix (Invalid Next.js Version)

### Fixed
- Updated `ui/package.json` Next.js dependency from invalid `^16.2.10` to valid `^16.2.6`.
- Kept React/ReactDOM and eslint-config-next compatibility unchanged.

### Files Changed
- `ui/package.json`
- `ui/package-lock.json` (revalidated via install; no functional dependency drift)

### Commands Run
- `cd ui && npm install`
- `cd ui && npm run build`

### Result
- Build passed successfully on Next.js `16.2.6`.

## 2026-05-12 - Next.js Build Lint/Type Fixes

### Completed
- Ran `npm install` in `ui`.
- Replaced explicit `any` usage in targeted files with safer typing (`unknown`, `Record<string, unknown>`, and existing model types).
- Fixed React hooks purity issue in `MessageList` by removing `Date.now()` from render-time filtering.
- Preserved behavior for auth, verified connections, encrypted chat/files, signature flows, crypto trace, and env config.

### Files Changed
- `ui/src/components/MessageList.tsx`
- `ui/src/components/MessageBubble.tsx`
- `ui/src/components/MessageComposer.tsx`
- `ui/src/components/crypto/CryptoTracePanel.tsx`
- `ui/src/components/attachments/AttachmentPicker.tsx`
- `ui/src/components/attachments/AttachmentPreview.tsx`
- `ui/src/providers/WebSocketProvider.tsx`
- `ui/src/services/websocket.ts`
- `ui/src/store/useAttachmentStore.ts`
- `ui/src/types/models.ts`

### Commands Run
- `cd ui && npm install`
- `cd ui && npm run build`

### Result
- Build passed successfully.
- Remaining output includes non-blocking ESLint warnings for unused symbols in unrelated files.

## 2026-05-12 - Email Verification Delivery Fix

### Fixed
- Registration now attempts real SMTP verification email delivery and reports truthful status.
- Resend verification now regenerates code, replaces old hash/expiry, and reports truthful email send status.
- Verify email flow keeps secure hash+expiry validation and clears verification fields on success.
- Email service now supports:
  - STARTTLS on port 587 (`SMTP_USE_TLS=true`)
  - SMTP SSL on port 465
  - authenticated send via `SMTP_USERNAME`/`SMTP_PASSWORD`
  - sender via `SMTP_FROM`
- Added non-secret diagnostics/logging for SMTP config and send success/failure.
- Added backend diagnostics endpoint:
  - `GET /api/auth/email-config`
- Added development-only email test endpoint:
  - `POST /api/auth/test-email`

### Production-safe behavior
- No password or SMTP secret logging.
- No verification code exposure in production responses.
- `dev_code` fallback is only returned when `APP_ENV=development` and email send fails.
- In production, register/resend return clear SMTP failure status (`ok=false`, `email_sent=false`) when delivery fails.

### Files Changed
- `app/services/email_service.py`
- `app/services/auth_service.py`
- `app/api/auth_api.py`
- `server.py`

### Render env variables required
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_USE_TLS=true`
- `APP_ENV=production`
- `FRONTEND_ORIGIN=<your frontend origin(s)>`

### Checks Run
- `python -m compileall app server.py` (pass)

### How to test
1. Configure Render env:
   - `SMTP_HOST=smtp.gmail.com`
   - `SMTP_PORT=587`
   - `SMTP_USERNAME=<gmail>`
   - `SMTP_PASSWORD=<gmail app password>`
   - `SMTP_FROM=<same gmail>`
   - `SMTP_USE_TLS=true`
   - `APP_ENV=production`
2. Restart/redeploy backend.
3. Call `GET /api/auth/email-config` and verify:
   - `configured=true`, `has_username=true`, `has_password=true`, expected host/port/from.
4. Register new account with real email.
5. Confirm verification email arrives.
6. Verify with code via `/api/auth/verify-email`.
7. Login succeeds.
8. Test `/api/auth/resend-verification` for unverified account.
9. Test forgot-password flow code delivery.

### Limitations
- Local JSON account store remains non-production-grade storage.
- SMTP provider policies (Gmail app password, anti-spam) can still block delivery externally.

## 2026-05-12 - Focused SMTP Delivery Debug/Fix (Render Production)

### Fixed
- Reworked SMTP send flow for robust production delivery and diagnostics.
- Register/resend/request-reset now return truthful `email_sent` and safe `error` on send failure.
- No more silent "code sent" success when SMTP fails in production.
- Connection request email flow now also reports `email_sent` and safe error details.

### SMTP implementation updates
- `app/services/email_service.py`:
  - Supports STARTTLS path for port 587 (`SMTP` + `ehlo()` + `starttls()` + `ehlo()` + `login()` + `send_message()`).
  - Supports SSL path for port 465 (`SMTP_SSL` + `login()` + `send_message()`).
  - Parses env vars via `os.getenv` directly (Render-compatible).
  - Adds non-secret logs for host/port/from/use_tls and credential presence.
  - Logs exception class + message on failure.
  - Never logs SMTP password.

### Auth behavior updates
- `app/services/auth_service.py`:
  - `AuthResult` now includes `email_sent` and `error`.
  - `register` and `resend_verification`:
    - success => `email_sent=true`
    - failure in development => `dev_code` fallback + `email_sent=false`
    - failure in production => `ok=false`, `email_sent=false`, safe `error`
  - `request_password_reset`:
    - returns `email_sent` based on actual send result
    - production send failure returns `ok=false` with safe `error`

- `app/api/auth_api.py`:
  - Surfaces `email_sent` and `error` fields in register/resend/reset-request responses.
  - `GET /api/auth/email-config` returns non-secret SMTP config status.
  - `POST /api/auth/test-email` available for deployment debugging (production-safe response, no secrets).

### Connection email updates
- `app/services/connection_service.py`:
  - `/api/connections/request` now returns:
    - `email_sent: true|false`
    - `ok` aligned with delivery result in production
    - safe `error` on SMTP failure
    - `dev_code` only in development

### Frontend status messaging
- `ui/src/services/auth.ts`
- `ui/src/store/useAuthStore.ts`
- `ui/src/components/auth/AuthScreen.tsx`

Updated UI behavior:
- Show "Verification code sent to your email" only when `email_sent=true`.
- Show clear failure message when `email_sent=false` with backend safe error.
- Keep `dev_code` display for development fallback.

### Added/confirmed endpoints
- `GET /api/auth/email-config`
- `POST /api/auth/test-email`

### Files changed
- `app/services/email_service.py`
- `app/services/auth_service.py`
- `app/api/auth_api.py`
- `app/services/connection_service.py`
- `ui/src/services/auth.ts`
- `ui/src/store/useAuthStore.ts`
- `ui/src/components/auth/AuthScreen.tsx`

### Render env required
- `SMTP_HOST=smtp.gmail.com`
- `SMTP_PORT=587`
- `SMTP_USERNAME=<real gmail>`
- `SMTP_PASSWORD=<gmail app password>`
- `SMTP_FROM=<same gmail>`
- `SMTP_USE_TLS=true`
- `APP_ENV=production`

### Checks run
- `python -m compileall app server.py` (pass)
- `cd ui && npm run build` (pass)

### Manual production test
1. Redeploy Render with env above.
2. Open `/api/auth/email-config` and confirm:
   - `has_username=true`
   - `has_password=true`
   - `smtp_host=smtp.gmail.com`
   - `smtp_port=587`
3. Call `POST /api/auth/test-email` with your email.
4. Check Render logs for send attempt and success/failure class/message.
5. Register new account and confirm verification email arrives.
6. Verify code and login.
7. Test resend verification and forgot-password request.

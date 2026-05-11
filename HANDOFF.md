# HANDOFF.md

## Current Status

Project has a working encrypted text-message path through FastAPI crypto bridge.

## Active Goal

Implement encrypted PDF sending and clickable crypto visualization panels.

## Task Board

### TASK-001 — Stabilize backend conversation API
Status: DONE

Notes:
- Implemented normalization for legacy profiles so the conversation API can
	load profiles that use `name` instead of `username` and return a normalized
	profile object.
- Made `profile_to_contact` tolerant of multiple profile shapes when building
	public contact cards.

Modified files:
- [app/api/conversation_api.py](app/api/conversation_api.py#L1-L200)

Executed checks:
- Started backend server and performed end-to-end encrypt/decrypt calls using
	the `/api/conversation/encrypt` and `/api/conversation/decrypt` endpoints
	(manual verification succeeded).

Remaining issues:
- Frontend integration still pending (TASK-004..TASK-010). No backend tracebacks
	seen for the stabilized conversation API.

### TASK-002 — Add encrypted file API
Status: DONE

Notes:
- Added `POST /api/conversation/encrypt-file` which accepts `sender`,
	`recipient`, `filename`, `mime_type`, and `content_b64` and currently only
	accepts `application/pdf` as `mime_type`.
- The endpoint validates base64 content, builds a serialized file payload and
	uses `ProtocolService.send_message(..., include_debug=True)` to produce an
	envelope. The response includes `envelope` and a `debug` object with
	`plaintext_size`, `ciphertext_size`, and `suite`.

Modified files:
- [app/api/conversation_api.py](app/api/conversation_api.py#L1-L260)

Executed checks:
- Restarted backend and performed manual POST to `/api/conversation/encrypt-file`.
- Verified encrypting a sample PDF-like payload (used a file as a bytes source)
	succeeded; response contained envelope and debug with sizes. No backend
	tracebacks observed.

Remaining issues:
- Frontend endpoints and UI changes remain (TASK-004..TASK-010).
- The endpoint currently enforces `application/pdf` only; add other types later if needed.

### TASK-003 — Update decrypt API to parse file payload
Status: DONE

Notes:
- Updated `/api/conversation/decrypt` to detect structured JSON payloads with
	`type: "file"` and return a `message` object containing `filename`,
	`mime_type`, `content_b64`, `size`, and `verified` instead of a raw
	plaintext string.

Modified files:
- [app/api/conversation_api.py](app/api/conversation_api.py#L1-L320)

Executed checks:
- Performed encrypt-file → decrypt round-trip using the backend; decrypt now
	returns the structured `message` object for file payloads. No tracebacks.

Remaining issues:
- UI must be updated to consume `message` responses for file messages and to
	render PDF bubbles (TASK-004..TASK-006).

### TASK-004 — Extend frontend message model
Status: DONE

Notes:
- Extended `ChatMessage` model to support file messages by adding `type`
	(`"text" | "file"`) and an optional `file` object with `filename`,
	`mimeType`, `size`, and optional `content_b64` for decrypted/local messages.
- Updated providers and composer to populate `type` and `file` where applicable
	(incoming WebSocket parsing and optimistic text messages).

Modified files:
- [ui/src/types/models.ts](ui/src/types/models.ts#L1-L200)
- [ui/src/providers/WebSocketProvider.tsx](ui/src/providers/WebSocketProvider.tsx#L1-L200)
- [ui/src/components/MessageComposer.tsx](ui/src/components/MessageComposer.tsx#L1-L200)

Executed checks:
- Built the frontend (`ui`) with `npm run build`; build completed successfully.

Remaining issues:
- UI rendering for PDF bubbles and the `CryptoTracePanel` component remain (TASK-005..TASK-007).

### TASK-005 — Add frontend PDF picker
Status: DONE

Notes:
- Implemented a PDF-only picker in the frontend to upload and encrypt PDFs.
- `AttachmentPicker` now reads the selected PDF, encodes it to base64, calls
	the backend `POST /api/conversation/encrypt-file` endpoint, and sends the
	returned `envelope` over the existing WebSocket transport (no plaintext
	bytes are sent over the socket).

Modified files:
- [ui/src/components/attachments/AttachmentPicker.tsx](ui/src/components/attachments/AttachmentPicker.tsx#L1-L240)
- [ui/src/services/attachments.ts](ui/src/services/attachments.ts#L1-L200) (unchanged APIs used)

Executed checks:
- Built the frontend (`npm run build`) — build succeeded.
- Manually tested the encrypt-file endpoint earlier; AttachmentPicker uses that
	endpoint and will send the envelope via WebSocket when used in the running
	app (manual integration test to follow when both servers and UI are running).

Remaining issues:
- UI bubble rendering for PDF messages and CryptoTracePanel are pending
	(TASK-006 and TASK-007).

### TASK-006 — Render PDF/file message bubble
Status: DONE

Notes:
- Added PDF rendering in the message UI: attachments with `mimeType: application/pdf`
	render as clickable bubbles showing filename and size.
- Clicking a PDF bubble opens a `CryptoTracePanel` modal displaying the
	envelope header and debug information (X25519/HKDF/ChaCha20 metadata) saved
	when the file was encrypted.

Modified files:
- [ui/src/components/attachments/AttachmentPreview.tsx](ui/src/components/attachments/AttachmentPreview.tsx#L1-L200)
- [ui/src/components/crypto/CryptoTracePanel.tsx](ui/src/components/crypto/CryptoTracePanel.tsx#L1-L200)
- [ui/src/store/useAttachmentStore.ts](ui/src/store/useAttachmentStore.ts#L1-L200)
- [ui/src/components/attachments/AttachmentPicker.tsx](ui/src/components/attachments/AttachmentPicker.tsx#L1-L240)
- [ui/src/types/models.ts](ui/src/types/models.ts#L1-L200)

Executed checks:
- Built the frontend after changes; build completed successfully.
- Attachment metadata now stores `envelope` and `debug` from the encrypt-file
	endpoint so the `CryptoTracePanel` can visualize encryption internals.

Remaining issues:
- If a received message arrives without attachment metadata (e.g., envelope
	only), the UI currently won't display trace info until decrypt flow populates
	the attachment store or message object with debug data (TASK-009).

### TASK-007 — Add CryptoTracePanel component

Status: TODO

### TASK-008 — Wire message click to visualization

Status: TODO

### TASK-009 — Decrypt received encrypted file message

Status: TODO

### TASK-010 — Manual test full flow

Status: TODO

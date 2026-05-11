# AGENT_UI_PROMPT.md

# SECURE MESSENGER FRONTEND CODEX AGENT

You are Codex acting as a senior frontend + systems engineer.

Your job is to understand this repository first, then continue implementing and stabilizing the frontend incrementally.

Do NOT rush.
Do NOT rewrite the backend.
Do NOT implement the entire frontend in one huge pass.

Work task-by-task using HANDOFF.md as the source of current progress.

---

# 1. REQUIRED FIRST ACTIONS

Before writing any code, you MUST read and understand:

1. HANDOFF.md
2. AGENT_UI_PROMPT.md
3. app/
4. ui/

Then inspect the current frontend implementation:

* ui/src/app
* ui/src/components
* ui/src/services
* ui/src/store
* ui/src/types
* ui/src/providers
* ui/package.json

Then inspect backend transport compatibility:

* app/transport
* app/core/packet_types.py
* app/services
* app/models

Do not start coding until you understand:

* current active task in HANDOFF.md
* completed tasks
* websocket packet schema
* existing frontend store structure
* existing component structure
* current build status

---

# 2. PROJECT OVERVIEW

This repository contains a Python secure messenger backend and a Next.js frontend.

Backend features include:

* websocket transport
* packet-based realtime communication
* message routing
* protocol service
* replay protection
* nonce management
* ratchet/session architecture
* typing indicators
* notifications
* contacts
* trust verification
* attachments
* queue/delivery/ack system

Frontend stack:

* Next.js App Router
* TypeScript
* Tailwind CSS
* shadcn/ui
* Radix UI
* Zustand

Backend websocket endpoint:

ws://localhost:8765

The frontend must communicate with the backend through websocket transport only.

---

# 3. ABSOLUTE RULES

## NEVER DO THIS

* Never rewrite backend architecture.
* Never invent REST APIs.
* Never replace websocket transport with REST.
* Never break existing packet schemas.
* Never disable TypeScript.
* Never introduce Redux.
* Never replace shadcn/ui with another UI framework.
* Never use Material UI.
* Never add fake permanent mock architecture.
* Never use `any` unless there is no safe alternative.
* Never leave build errors unresolved.
* Never create giant monolithic components.
* Never modify unrelated backend code to make frontend easier.

## ALWAYS DO THIS

* Always preserve backend compatibility.
* Always use websocket transport.
* Always use strict TypeScript.
* Always keep components modular.
* Always use Zustand for global state.
* Always use hooks for logic.
* Always use shadcn/ui where appropriate.
* Always run build validation after meaningful changes.
* Always update HANDOFF.md after completing a task.
* Always continue from CURRENT ACTIVE TASK in HANDOFF.md.
* Always fix the first real build error before moving on.

---

# 4. CODEBASE ORIENTATION

## Backend root

app/

Important backend areas:

app/
├── core/
├── services/
├── transport/
├── storage/
├── models/
└── profiles/

Important backend concepts:

* TransportPacket
* PacketType
* websocket transport server
* typing packets
* notification events
* presence packets
* ack packets
* message packets
* attachment packets
* trust/profile/contact structures

## Frontend root

ui/

Important frontend areas:

ui/src/
├── app/
├── components/
├── hooks/
├── providers/
├── services/
├── store/
├── types/
└── lib/

Before adding a file, check whether an equivalent file already exists.

---

# 5. TASK EXECUTION MODEL

This project uses HANDOFF.md as persistent agent memory.

You MUST follow this workflow:

1. Read HANDOFF.md.
2. Identify CURRENT ACTIVE TASK.
3. Implement only that task.
4. Run validation.
5. Fix all errors.
6. Update HANDOFF.md.
7. Activate the next task.
8. Stop or continue only if instructed.

Do not restart planning from zero.

Do not redo completed tasks unless there is a build/runtime issue.

---

# 6. VALIDATION COMMANDS

Frontend validation:

```bash
cd ui
npm run build
```

Use webpack build, not Turbopack.

package.json should use:

```json
"build": "next build --webpack"
```

If build hangs:

1. stop node process
2. delete `.next`
3. rerun build
4. inspect circular imports
5. inspect client/server component mismatch
6. inspect infinite render loops

Backend validation when needed:

```bash
python -m tests.run_system_validation
```

Backend server:

```bash
python main.py server
```

Frontend dev server:

```bash
cd ui
npm run dev
```

---

# 7. WEBSOCKET REQUIREMENTS

Frontend websocket must remain compatible with backend websocket transport.

Required websocket behavior:

* connect to ws://localhost:8765
* send connect packet if backend expects it
* safe JSON parsing
* typed packet handling
* reconnect with backoff
* heartbeat/ping if supported
* packet dispatching
* graceful disconnect
* connection state store
* no duplicate listeners
* no memory leaks

Do not invent a new protocol.

Before changing websocket code, inspect:

* app/transport/transport_server.py
* app/transport/transport_packet.py
* app/core/packet_types.py
* ui/src/services/websocket.ts
* ui/src/providers/WebSocketProvider.tsx
* ui/src/types/packets.ts

---

# 8. FRONTEND ARCHITECTURE RULES

Expected frontend structure:

ui/src/
├── app/
├── components/
│   ├── chat/
│   ├── contacts/
│   ├── notifications/
│   ├── trust/
│   ├── attachments/
│   ├── settings/
│   └── ui/
├── hooks/
├── providers/
├── services/
├── store/
├── types/
└── lib/

Rules:

* Components should be small and focused.
* Business logic belongs in hooks/services/stores.
* Global state belongs in Zustand stores.
* Transport logic belongs in services/providers.
* Domain types belong in types/.
* Shared utilities belong in lib/.
* Avoid files over 300 lines unless unavoidable.

---

# 9. TYPESCRIPT RULES

Use strict TypeScript.

Avoid:

```ts
any
```

Prefer:

```ts
unknown
Record<string, unknown>
typed discriminated unions
typed payload interfaces
```

Required type files may include:

types/
├── packets.ts
├── models.ts
├── messages.ts
├── contacts.ts
├── websocket.ts
├── attachments.ts
└── trust.ts

Transport packet types must match backend packet schema.

Delivery state must support frontend and backend lifecycle states, for example:

* pending
* queued
* sending
* sent
* delivered
* acked
* read
* failed
* expired
* dropped

Only include states actually used by frontend/backend.

---

# 10. UI DESIGN TARGET

Target UX quality:

* Signal Desktop
* Telegram Desktop
* Discord
* Session Messenger

Design style:

* dark-mode first
* clean spacing
* rounded-xl / rounded-2xl
* subtle borders
* soft hover states
* smooth transitions
* responsive layout
* desktop-quality chat experience
* mobile-friendly sidebar
* accessible dialogs

---

# 11. PERFORMANCE RULES

Optimize for:

* minimal rerenders
* granular Zustand selectors
* memoized message bubbles
* stable websocket event subscriptions
* stable autoscroll
* lazy loading heavy UI
* no excessive localStorage writes
* no duplicate timers
* no leaked object URLs

For attachments:

* revoke object URLs when no longer needed
* avoid storing large binary data in Zustand
* store metadata and preview URLs only

---

# 12. ACCESSIBILITY RULES

Every interactive icon button needs:

* aria-label
* focus-visible style
* keyboard accessibility

Dialogs should have:

* accessible labels
* escape close behavior
* focus management
* mobile-safe layout

Keyboard UX should support where appropriate:

* Esc closes overlays/dialogs
* Ctrl/Cmd + K focuses search
* Enter activates selected item
* Shift + Enter creates newline in composer
* Enter sends message in composer

---

# 13. TASK ORDER

Follow HANDOFF.md first.

If HANDOFF.md is missing or incomplete, use this order:

1. Chat layout
2. Conversation sidebar
3. Message list UI
4. Websocket foundation
5. Realtime messages
6. Zustand stores
7. Typing indicators
8. Notifications
9. Contacts UI
10. Trust verification
11. Attachments
12. Settings
13. Responsiveness and polish
14. Integration validation
15. Production hardening

---

# 14. COMPLETION CRITERIA PER TASK

A task is complete only when:

1. Implementation is finished.
2. `npm run build` passes.
3. No TypeScript errors remain.
4. No obvious runtime issues remain.
5. HANDOFF.md is updated.
6. The next task is activated.

Do not mark a task complete if build has not passed.

---

# 15. HANDOFF UPDATE RULES

After completing a task, update HANDOFF.md:

* Move current task to COMPLETED TASKS.
* Add files created/modified.
* Add build result.
* Add known issues.
* Set next task as CURRENT ACTIVE TASK.
* Preserve previous completed task history.
* Preserve backend compatibility notes.

If all tasks are complete, set:

FINAL STATUS: COMPLETE

and include:

* frontend architecture summary
* implemented features summary
* final validation status
* known limitations

---

# 16. DEBUGGING LOOP

When build fails:

1. Read the first real error.
2. Fix only that error.
3. Run build again.
4. Repeat.

Do not blindly rewrite large parts of the app.

When websocket fails:

1. Check backend server is running.
2. Check ws://localhost:8765.
3. Check packet schema.
4. Check browser console.
5. Check backend logs.
6. Add targeted logging.
7. Fix lifecycle mismatch.

When TypeScript complains about types:

1. Inspect the real type source.
2. Align callers to existing types.
3. Avoid unsafe casts.
4. Prefer improving shared type definitions.

---

# 17. POST-FRONTEND STABILIZATION

After all UI tasks complete, enter stabilization mode.

Validate:

* websocket connection
* reconnect
* typing indicators
* notifications
* contacts
* trust badges
* attachments
* settings persistence
* mobile layout
* desktop layout
* accessibility
* production build

Then create or update:

* README_FRONTEND.md
* DEPLOYMENT.md
* .env.example

---

# 18. CURRENT AGENT EXECUTION INSTRUCTION

When Codex starts:

1. Read AGENT_UI_PROMPT.md.
2. Read HANDOFF.md.
3. Inspect the actual codebase.
4. Continue only from CURRENT ACTIVE TASK.
5. Implement incrementally.
6. Run `npm run build`.
7. Fix errors.
8. Update HANDOFF.md.
9. Continue to next task only after the current task is stable.

Do not ask for confirmation between subtasks unless there is a blocking architectural decision.

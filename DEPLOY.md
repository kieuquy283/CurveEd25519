# Deployment Guide

This project is split deployment:
- Frontend: Next.js on Vercel
- Backend: FastAPI + WebSocket server on a persistent host (VPS/Render/Railway)

Do **not** deploy the FastAPI/WebSocket backend to Vercel.
WebSocket transport requires a long-running process.

## 1. Frontend (Vercel)

1. Push repo to GitHub.
2. Import project in Vercel.
3. Set root directory to `ui`.
4. Build command: `npm run build`
5. Output: Next.js default
6. Configure environment variables in Vercel:
   - `NEXT_PUBLIC_API_BASE_URL=https://<your-backend-domain>`
   - `NEXT_PUBLIC_WS_URL=wss://<your-ws-domain-or-path>`
7. Deploy.

## 2. Backend (VPS / Render / Railway)

Deploy Python backend from repo root with a persistent process manager.

Required environment variables:
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_USE_TLS=true`
- `APP_ENV=production`
- `FRONTEND_ORIGIN=https://<your-vercel-app>.vercel.app`

You may provide multiple frontend origins via comma-separated value:
- `FRONTEND_ORIGIN=https://app.vercel.app,https://www.example.com`

Run backend API server (example):
```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

Run WebSocket transport server (example):
```bash
python main.py run-server --host 0.0.0.0 --port 8765
```

## 3. Local Development

Backend API:
```bash
uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

Backend WebSocket server:
```bash
python main.py run-server --host 127.0.0.1 --port 8765
```

Frontend:
```bash
cd ui
npm install
npm run dev
```

Local defaults used by frontend when env vars are missing:
- API: `http://127.0.0.1:8000`
- WS: `ws://127.0.0.1:8765`

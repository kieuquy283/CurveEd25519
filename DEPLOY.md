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

## Supabase Persistent Storage (Render Backend)

Set these backend env vars on Render:
- `STORAGE_BACKEND=supabase`
- `SUPABASE_URL=https://<project>.supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY=<service-role-key>`
- `APP_ENV=production`
- `FRONTEND_ORIGIN=https://curve-ed25519.vercel.app`
- `EMAIL_PROVIDER=resend`
- `RESEND_API_KEY=<resend-key>`
- `EMAIL_FROM=<verified-sender>`

Security notes:
- `SUPABASE_SERVICE_ROLE_KEY` is backend-only.
- Do not put service role key in Vercel env.
- Do not commit service role key to git.

SQL setup (run in Supabase SQL Editor):
```sql
create table if not exists app_accounts (
  email text primary key,
  display_name text,
  password_hash text not null,
  verified boolean not null default false,
  created_at timestamptz,
  updated_at timestamptz,
  verification_code_hash text,
  verification_expires_at timestamptz,
  reset_code_hash text,
  reset_expires_at timestamptz,
  profile_id text
);

create table if not exists app_profiles (
  email text primary key,
  profile_json jsonb not null,
  created_at timestamptz,
  updated_at timestamptz
);

create table if not exists app_connections (
  id text primary key,
  status text,
  requester_email text,
  recipient_email text,
  connection_json jsonb,
  verification_code_hash text,
  verification_expires_at timestamptz,
  created_at timestamptz,
  verified_at timestamptz
);

create table if not exists app_signed_files (
  id text primary key,
  owner_email text,
  filename text,
  signed_file_json jsonb,
  created_at timestamptz
);
```

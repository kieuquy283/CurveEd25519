from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StorageRepository:
    def __init__(self, *, data_dir: str = "data") -> None:
        self.storage_backend = (os.getenv("STORAGE_BACKEND") or "file").strip().lower()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.accounts_path = self.data_dir / "accounts.json"
        self.profiles_path = self.data_dir / "profiles.json"
        self.connections_path = self.data_dir / "connections.json"
        self.signed_files_path = self.data_dir / "signed_files.json"
        self.supabase_url = (os.getenv("SUPABASE_URL") or "").strip()
        self.supabase_key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        self.app_env = (os.getenv("APP_ENV") or "development").strip().lower()
        self._supabase = None

        if self.storage_backend != "supabase":
            self._ensure_file_store()
            return

        if not self.supabase_url or not self.supabase_key:
            if self.app_env == "production":
                raise RuntimeError("STORAGE_BACKEND=supabase requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
            self.storage_backend = "file"
            self._ensure_file_store()
            return

        from supabase import create_client  # type: ignore

        self._supabase = create_client(self.supabase_url, self.supabase_key)

    def _ensure_file_store(self) -> None:
        for p in [self.accounts_path, self.profiles_path, self.connections_path, self.signed_files_path]:
            if not p.exists():
                p.write_text("[]", encoding="utf-8")

    @staticmethod
    def _norm_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def is_supabase(self) -> bool:
        return self.storage_backend == "supabase" and self._supabase is not None

    def _read_rows(self, path: Path) -> list[dict[str, Any]]:
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            rows = []
        if not isinstance(rows, list):
            return []
        return [r for r in rows if isinstance(r, dict)]

    def _write_rows(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    # Accounts
    def list_accounts(self) -> list[dict[str, Any]]:
        if self.is_supabase():
            resp = self._supabase.table("app_accounts").select("*").execute()
            return list(resp.data or [])
        return self._read_rows(self.accounts_path)

    def get_account(self, email: str) -> dict[str, Any] | None:
        norm = self._norm_email(email)
        if self.is_supabase():
            resp = self._supabase.table("app_accounts").select("*").eq("email", norm).limit(1).execute()
            data = list(resp.data or [])
            return data[0] if data else None
        for row in self._read_rows(self.accounts_path):
            if str(row.get("email") or "").strip().lower() == norm:
                return row
        return None

    def upsert_account(self, account: dict[str, Any]) -> None:
        account = dict(account)
        account["email"] = self._norm_email(str(account.get("email") or ""))
        if not account["email"]:
            return
        if self.is_supabase():
            self._supabase.table("app_accounts").upsert(account, on_conflict="email").execute()
            return
        rows = self._read_rows(self.accounts_path)
        replaced = False
        for i, row in enumerate(rows):
            if str(row.get("email") or "").strip().lower() == account["email"]:
                rows[i] = account
                replaced = True
                break
        if not replaced:
            rows.append(account)
        self._write_rows(self.accounts_path, rows)

    def replace_accounts(self, accounts: list[dict[str, Any]]) -> None:
        if self.is_supabase():
            for account in accounts:
                self.upsert_account(account)
            return
        self._write_rows(self.accounts_path, accounts)

    # Profiles
    def get_profile(self, email: str) -> dict[str, Any] | None:
        norm = self._norm_email(email)
        if self.is_supabase():
            resp = self._supabase.table("app_profiles").select("*").eq("email", norm).limit(1).execute()
            data = list(resp.data or [])
            if not data:
                return None
            return data[0].get("profile_json")
        rows = self._read_rows(self.profiles_path)
        for row in rows:
            if str(row.get("email") or "").strip().lower() == norm:
                return row.get("profile_json")
        return None

    def upsert_profile(self, email: str, profile_json: dict[str, Any]) -> None:
        norm = self._norm_email(email)
        payload = {
            "email": norm,
            "profile_json": profile_json,
            "updated_at": self._now_iso(),
        }
        if self.is_supabase():
            if self.get_profile(norm) is None:
                payload["created_at"] = self._now_iso()
            self._supabase.table("app_profiles").upsert(payload, on_conflict="email").execute()
            return
        rows = self._read_rows(self.profiles_path)
        replaced = False
        for i, row in enumerate(rows):
            if str(row.get("email") or "").strip().lower() == norm:
                rows[i] = payload
                replaced = True
                break
        if not replaced:
            payload["created_at"] = self._now_iso()
            rows.append(payload)
        self._write_rows(self.profiles_path, rows)

    # Connections
    def list_connections(self) -> list[dict[str, Any]]:
        if self.is_supabase():
            resp = self._supabase.table("app_connections").select("*").execute()
            out: list[dict[str, Any]] = []
            for row in list(resp.data or []):
                conn = dict(row.get("connection_json") or {})
                if not conn and row.get("id"):
                    conn = {"id": row.get("id")}
                conn["id"] = row.get("id")
                conn["status"] = row.get("status")
                conn["requester_email"] = row.get("requester_email")
                conn["recipient_email"] = row.get("recipient_email")
                conn["verification_code_hash"] = row.get("verification_code_hash")
                conn["verification_expires_at"] = row.get("verification_expires_at")
                conn["created_at"] = row.get("created_at")
                conn["verified_at"] = row.get("verified_at")
                out.append(conn)
            return out
        return self._read_rows(self.connections_path)

    def upsert_connection(self, conn: dict[str, Any]) -> None:
        if self.is_supabase():
            payload = {
                "id": conn.get("id"),
                "status": conn.get("status"),
                "requester_email": self._norm_email(str(conn.get("requester_email") or "")),
                "recipient_email": self._norm_email(str(conn.get("recipient_email") or "")),
                "connection_json": conn,
                "verification_code_hash": conn.get("verification_code_hash"),
                "verification_expires_at": conn.get("verification_expires_at"),
                "created_at": conn.get("created_at"),
                "verified_at": conn.get("verified_at"),
            }
            self._supabase.table("app_connections").upsert(payload, on_conflict="id").execute()
            return
        rows = self._read_rows(self.connections_path)
        replaced = False
        for i, row in enumerate(rows):
            if row.get("id") == conn.get("id"):
                rows[i] = conn
                replaced = True
                break
        if not replaced:
            rows.append(conn)
        self._write_rows(self.connections_path, rows)

    def replace_connections(self, rows: list[dict[str, Any]]) -> None:
        if self.is_supabase():
            for row in rows:
                self.upsert_connection(row)
            return
        self._write_rows(self.connections_path, rows)

    def save_signed_file(self, record: dict[str, Any]) -> None:
        if self.is_supabase():
            self._supabase.table("app_signed_files").upsert(record, on_conflict="id").execute()
            return
        rows = self._read_rows(self.signed_files_path)
        rows.append(record)
        self._write_rows(self.signed_files_path, rows)

    def debug_storage(self) -> dict[str, Any]:
        out = {
            "ok": True,
            "storage_backend": "supabase" if self.is_supabase() else "file",
            "has_supabase_url": bool(self.supabase_url),
            "has_service_role_key": bool(self.supabase_key),
            "account_count": None,
            "profile_count": None,
            "connection_count": None,
            "signed_file_count": None,
        }
        if self.is_supabase():
            try:
                out["account_count"] = len(self.list_accounts())
            except Exception:
                out["account_count"] = None
            try:
                out["profile_count"] = len([r for r in self._supabase.table("app_profiles").select("email").execute().data or []])
            except Exception:
                out["profile_count"] = None
            try:
                out["connection_count"] = len(self.list_connections())
            except Exception:
                out["connection_count"] = None
            try:
                out["signed_file_count"] = len([r for r in self._supabase.table("app_signed_files").select("id").execute().data or []])
            except Exception:
                out["signed_file_count"] = None
        else:
            out["account_count"] = len(self._read_rows(self.accounts_path))
            out["profile_count"] = len(self._read_rows(self.profiles_path))
            out["connection_count"] = len(self._read_rows(self.connections_path))
            out["signed_file_count"] = len(self._read_rows(self.signed_files_path))
        return out

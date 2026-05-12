from __future__ import annotations

import json
import os
import re
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
        self._missing_account_columns: set[str] = set()

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

    @staticmethod
    def _log(message: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        print(f"[storage][{ts}] {message}")

    @staticmethod
    def _extract_missing_column(error_text: str) -> str | None:
        match = re.search(r"Could not find the '([^']+)' column", error_text)
        if not match:
            return None
        return match.group(1)

    # Accounts
    def list_accounts(self) -> list[dict[str, Any]]:
        if self.is_supabase():
            resp = self._supabase.table("app_accounts").select("*").execute()
            rows = list(resp.data or [])
            out: list[dict[str, Any]] = []
            for row in rows:
                account = dict(row)
                metadata = account.get("metadata")
                if isinstance(metadata, dict):
                    for key in ["user_id", "verification_code_hash", "verification_expires_at", "reset_code_hash", "reset_expires_at", "profile_id"]:
                        if key not in account and key in metadata:
                            account[key] = metadata.get(key)
                out.append(account)
            return out
        return self._read_rows(self.accounts_path)

    def get_account(self, email: str) -> dict[str, Any] | None:
        norm = self._norm_email(email)
        if self.is_supabase():
            resp = self._supabase.table("app_accounts").select("*").eq("email", norm).limit(1).execute()
            data = list(resp.data or [])
            if not data:
                return None
            account = dict(data[0])
            metadata = account.get("metadata")
            if isinstance(metadata, dict):
                for key in ["user_id", "verification_code_hash", "verification_expires_at", "reset_code_hash", "reset_expires_at", "profile_id"]:
                    if key not in account and key in metadata:
                        account[key] = metadata.get(key)
            return account
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
            base_columns = [
                "email",
                "user_id",
                "display_name",
                "password_hash",
                "verified",
                "created_at",
                "updated_at",
                "verification_code_hash",
                "verification_expires_at",
                "reset_code_hash",
                "reset_expires_at",
                "profile_id",
                "metadata",
            ]
            payload: dict[str, Any] = {}
            for col in base_columns:
                if col in self._missing_account_columns:
                    continue
                if col == "metadata":
                    continue
                if col in account:
                    payload[col] = account.get(col)

            legacy_fields = {
                k: v
                for k, v in account.items()
                if k not in set(base_columns) and k not in {"password_hash"}
            }
            metadata = account.get("metadata") if isinstance(account.get("metadata"), dict) else {}
            if isinstance(metadata, dict):
                metadata = dict(metadata)
            else:
                metadata = {}
            metadata.update(legacy_fields)
            if "metadata" not in self._missing_account_columns:
                payload["metadata"] = metadata

            self._log(f"supabase upsert app_accounts payload_keys={sorted(payload.keys())}")
            try:
                self._supabase.table("app_accounts").upsert(payload, on_conflict="email").execute()
            except Exception as exc:
                err_text = str(exc)
                missing = self._extract_missing_column(err_text)
                if missing:
                    self._missing_account_columns.add(missing)
                    self._log(f"app_accounts missing column detected: {missing}; retrying without it")
                    payload.pop(missing, None)
                    if missing != "metadata":
                        meta = payload.get("metadata")
                        if isinstance(meta, dict) and missing in account:
                            meta[missing] = account.get(missing)
                    self._log(f"supabase retry app_accounts payload_keys={sorted(payload.keys())}")
                    self._supabase.table("app_accounts").upsert(payload, on_conflict="email").execute()
                else:
                    raise
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

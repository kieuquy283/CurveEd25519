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
        self.conversations_path = self.data_dir / "conversations.json"
        self.messages_path = self.data_dir / "messages.json"
        self.notifications_path = self.data_dir / "notifications.json"
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
        for p in [
            self.accounts_path,
            self.profiles_path,
            self.connections_path,
            self.signed_files_path,
            self.conversations_path,
            self.messages_path,
            self.notifications_path,
        ]:
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

    # Conversations / messages
    def get_or_create_conversation(self, user_a: str, user_b: str, connection_id: str | None = None) -> dict[str, Any]:
        a = self._norm_email(user_a)
        b = self._norm_email(user_b)
        pair = {a, b}
        if self.is_supabase():
            rows = list(
                self._supabase.table("app_conversations").select("*").or_(
                    f"and(user_a_email.eq.{a},user_b_email.eq.{b}),and(user_a_email.eq.{b},user_b_email.eq.{a})"
                ).limit(1).execute().data or []
            )
            if rows:
                return dict(rows[0])
            import secrets
            now = self._now_iso()
            conv = {
                "id": secrets.token_hex(12),
                "user_a_email": a,
                "user_b_email": b,
                "connection_id": connection_id,
                "created_at": now,
                "updated_at": now,
                "last_message_at": None,
                "last_message_preview": None,
            }
            self._supabase.table("app_conversations").upsert(conv, on_conflict="id").execute()
            return conv
        rows = self._read_rows(self.conversations_path)
        for row in rows:
            if {self._norm_email(str(row.get("user_a_email") or "")), self._norm_email(str(row.get("user_b_email") or ""))} == pair:
                return row
        import secrets
        now = self._now_iso()
        conv = {
            "id": secrets.token_hex(12),
            "user_a_email": a,
            "user_b_email": b,
            "connection_id": connection_id,
            "created_at": now,
            "updated_at": now,
            "last_message_at": None,
            "last_message_preview": None,
        }
        rows.append(conv)
        self._write_rows(self.conversations_path, rows)
        return conv

    def list_conversations(self, user_email: str) -> list[dict[str, Any]]:
        user = self._norm_email(user_email)
        if self.is_supabase():
            data = list(
                self._supabase.table("app_conversations")
                .select("*")
                .or_(f"user_a_email.eq.{user},user_b_email.eq.{user}")
                .execute()
                .data
                or []
            )
            return data
        rows = self._read_rows(self.conversations_path)
        return [
            row for row in rows
            if self._norm_email(str(row.get("user_a_email") or "")) == user
            or self._norm_email(str(row.get("user_b_email") or "")) == user
        ]

    def save_message(self, message_record: dict[str, Any]) -> dict[str, Any]:
        rec = dict(message_record)
        rec["sender_email"] = self._norm_email(str(rec.get("sender_email") or ""))
        rec["receiver_email"] = self._norm_email(str(rec.get("receiver_email") or ""))
        if self.is_supabase():
            self._supabase.table("app_messages").upsert(rec, on_conflict="id").execute()
            # update conversation latest fields
            if rec.get("conversation_id"):
                self._supabase.table("app_conversations").update({
                    "updated_at": self._now_iso(),
                    "last_message_at": rec.get("created_at") or self._now_iso(),
                    "last_message_preview": rec.get("plaintext_preview"),
                }).eq("id", rec["conversation_id"]).execute()
            return rec
        rows = self._read_rows(self.messages_path)
        replaced = False
        for i, row in enumerate(rows):
            if row.get("id") == rec.get("id") or (row.get("packet_id") and row.get("packet_id") == rec.get("packet_id")):
                rows[i] = rec
                replaced = True
                break
        if not replaced:
            rows.append(rec)
        self._write_rows(self.messages_path, rows)
        return rec

    def list_messages(self, conversation_id: str, user_email: str, limit: int = 50) -> list[dict[str, Any]]:
        user = self._norm_email(user_email)
        if self.is_supabase():
            conv_rows = list(self._supabase.table("app_conversations").select("*").eq("id", conversation_id).limit(1).execute().data or [])
            if not conv_rows:
                return []
            conv = conv_rows[0]
            if user not in {self._norm_email(str(conv.get("user_a_email") or "")), self._norm_email(str(conv.get("user_b_email") or ""))}:
                return []
            data = list(
                self._supabase.table("app_messages")
                .select("*")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
                .data
                or []
            )
            return data
        convs = self._read_rows(self.conversations_path)
        conv = next((c for c in convs if c.get("id") == conversation_id), None)
        if not conv:
            return []
        if user not in {self._norm_email(str(conv.get("user_a_email") or "")), self._norm_email(str(conv.get("user_b_email") or ""))}:
            return []
        rows = [r for r in self._read_rows(self.messages_path) if r.get("conversation_id") == conversation_id]
        rows.sort(key=lambda x: str(x.get("created_at") or ""))
        return rows[-limit:]

    # Notifications
    def create_notification(self, notif: dict[str, Any]) -> dict[str, Any]:
        record = dict(notif)
        record["user_email"] = self._norm_email(str(record.get("user_email") or ""))
        if self.is_supabase():
            self._supabase.table("app_notifications").upsert(record, on_conflict="id").execute()
            return record
        rows = self._read_rows(self.notifications_path)
        rows.append(record)
        self._write_rows(self.notifications_path, rows)
        return record

    def list_notifications(self, user_email: str) -> list[dict[str, Any]]:
        user = self._norm_email(user_email)
        if self.is_supabase():
            data = list(
                self._supabase.table("app_notifications")
                .select("*")
                .eq("user_email", user)
                .order("created_at", desc=True)
                .execute()
                .data
                or []
            )
            return data
        rows = [r for r in self._read_rows(self.notifications_path) if self._norm_email(str(r.get("user_email") or "")) == user]
        rows.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
        return rows

    def mark_notification_read(self, notif_id: str) -> None:
        if self.is_supabase():
            self._supabase.table("app_notifications").update({"read": True}).eq("id", notif_id).execute()
            return
        rows = self._read_rows(self.notifications_path)
        for row in rows:
            if row.get("id") == notif_id:
                row["read"] = True
                break
        self._write_rows(self.notifications_path, rows)

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
            "conversation_count": None,
            "message_count": None,
            "notification_count": None,
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
            try:
                out["conversation_count"] = len([r for r in self._supabase.table("app_conversations").select("id").execute().data or []])
            except Exception:
                out["conversation_count"] = None
            try:
                out["message_count"] = len([r for r in self._supabase.table("app_messages").select("id").execute().data or []])
            except Exception:
                out["message_count"] = None
            try:
                out["notification_count"] = len([r for r in self._supabase.table("app_notifications").select("id").execute().data or []])
            except Exception:
                out["notification_count"] = None
        else:
            out["account_count"] = len(self._read_rows(self.accounts_path))
            out["profile_count"] = len(self._read_rows(self.profiles_path))
            out["connection_count"] = len(self._read_rows(self.connections_path))
            out["signed_file_count"] = len(self._read_rows(self.signed_files_path))
            out["conversation_count"] = len(self._read_rows(self.conversations_path))
            out["message_count"] = len(self._read_rows(self.messages_path))
            out["notification_count"] = len(self._read_rows(self.notifications_path))
        return out

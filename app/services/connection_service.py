from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.profiles.profile_service import ProfileService
from app.services.crypto_service import CryptoService
from app.services.storage_repository import StorageRepository


class ConnectionService:
    def __init__(
        self,
        *,
        connections_path: str = "data/connections.json",
        accounts_path: str = "data/accounts.json",
        profiles_dir: str = "data/profiles",
    ) -> None:
        self.connections_path = Path(connections_path)
        self.connections_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.connections_path.exists():
            self.connections_path.write_text("[]", encoding="utf-8")

        self.auth_service = AuthService(accounts_path=accounts_path, profiles_dir=profiles_dir)
        self.email_service = EmailService()
        self.profile_service = ProfileService(profiles_dir=profiles_dir)
        self.storage = StorageRepository(data_dir=str(self.connections_path.parent))

        env = (os.getenv("APP_ENV") or os.getenv("ENV") or os.getenv("PYTHON_ENV") or "development").lower()
        self.is_development = env in {"dev", "development", "local", "test"}
        self.code_pepper = (os.getenv("CONNECTION_CODE_PEPPER") or os.getenv("AUTH_CODE_PEPPER") or "curveapp-connection-pepper").encode("utf-8")

    @staticmethod
    def _notification_id() -> str:
        return secrets.token_hex(12)

    def request_connection(self, *, from_user: str, to: str) -> dict[str, Any]:
        requester = self._resolve_user(from_user)
        recipient = self._resolve_user(to)

        if requester["email"] == recipient["email"]:
            raise ValueError("Self connection is not allowed")

        requester_profile = self._profile_for_email(requester["email"])
        recipient_profile = self._profile_for_email(recipient["email"])

        connections = self._load_connections()
        existing = self._find_pair(connections, requester["email"], recipient["email"])

        code = self._generate_code()
        now = self._utc_now()

        if existing and existing.get("status") == "verified":
            self._refresh_key_snapshot(existing, requester, recipient, requester_profile, recipient_profile)
            self._save_connections(connections)
            return {"ok": True, "status": "verified", "connection_id": existing["id"], "message": "Already verified"}

        if existing is None:
            existing = {
                "id": secrets.token_hex(12),
                "status": "pending",
                "requester_id": requester["user_id"],
                "requester_email": requester["email"],
                "recipient_id": recipient["user_id"],
                "recipient_email": recipient["email"],
                "requester_x25519_public_key": "",
                "requester_ed25519_public_key": "",
                "recipient_x25519_public_key": "",
                "recipient_ed25519_public_key": "",
                "requester_key_fingerprint": "",
                "recipient_key_fingerprint": "",
                "verification_code_hash": None,
                "verification_expires_at": None,
                "created_at": now,
                "verified_at": None,
            }
            connections.append(existing)

        self._refresh_key_snapshot(existing, requester, recipient, requester_profile, recipient_profile)
        existing["status"] = "pending"
        existing["verification_code_hash"] = self._hash_code(code)
        existing["verification_expires_at"] = self._iso_now_plus(minutes=10)

        self._save_connections(connections)

        sent = self._send_connection_email(recipient["email"], requester["email"], code)
        response: dict[str, Any] = {
            "ok": sent or self.is_development,
            "status": "pending",
            "connection_id": existing["id"],
            "message": "Connection verification code sent" if sent else "Could not send connection verification email.",
            "email_sent": sent,
        }
        if self.is_development and not sent:
            response["dev_code"] = code
        if not sent:
            err = self.email_service.last_error or "SMTP send failed"
            cls = self.email_service.last_error_class or "SMTPError"
            response["error"] = f"{cls}: {err}"
        self.storage.create_notification(
            {
                "id": self._notification_id(),
                "user_email": recipient["email"],
                "type": "connection_request",
                "title": "Yêu cầu kết nối mới",
                "body": f"{requester['email']} muốn kết nối với bạn",
                "data": {
                    "peerEmail": requester["email"],
                    "peerDisplayName": requester.get("display_name") or requester["email"],
                    "connectionId": existing["id"],
                    "status": "pending",
                },
                "read": False,
                "created_at": self._utc_now(),
            }
        )
        return response

    def verify_connection(self, *, connection_id: str, user: str, code: str) -> dict[str, Any]:
        verifier = self._resolve_user(user)
        connections = self._load_connections()
        conn = next((c for c in connections if c.get("id") == connection_id), None)
        if not conn:
            raise ValueError("Connection not found")

        if verifier["email"] not in {conn.get("requester_email"), conn.get("recipient_email")}:
            raise ValueError("User is not part of this connection")

        self._validate_code(conn.get("verification_code_hash"), conn.get("verification_expires_at"), code)

        requester = self._resolve_user(conn["requester_email"])
        recipient = self._resolve_user(conn["recipient_email"])
        requester_profile = self._profile_for_email(requester["email"])
        recipient_profile = self._profile_for_email(recipient["email"])
        self._refresh_key_snapshot(conn, requester, recipient, requester_profile, recipient_profile)

        conn["status"] = "verified"
        conn["verified_at"] = self._utc_now()
        conn["verification_code_hash"] = None
        conn["verification_expires_at"] = None
        conn["connection_json"] = self._build_connection_json(
            requester=requester,
            recipient=recipient,
            requester_profile=requester_profile,
            recipient_profile=recipient_profile,
            verified_at=conn["verified_at"],
            trusted=True,
        )
        self._save_connections(connections)
        self.storage.create_notification(
            {
                "id": self._notification_id(),
                "user_email": requester["email"],
                "type": "connection_verified",
                "title": "Kết nối đã xác minh",
                "body": f"Bạn có thể nhắn tin an toàn với {recipient['email']}",
                "data": {
                    "peerEmail": recipient["email"],
                    "peerDisplayName": recipient.get("display_name") or recipient["email"],
                    "connectionId": conn["id"],
                    "status": "verified",
                },
                "read": False,
                "created_at": self._utc_now(),
            }
        )
        self.storage.create_notification(
            {
                "id": self._notification_id(),
                "user_email": recipient["email"],
                "type": "connection_verified",
                "title": "Kết nối đã xác minh",
                "body": f"Bạn có thể nhắn tin an toàn với {requester['email']}",
                "data": {
                    "peerEmail": requester["email"],
                    "peerDisplayName": requester.get("display_name") or requester["email"],
                    "connectionId": conn["id"],
                    "status": "verified",
                },
                "read": False,
                "created_at": self._utc_now(),
            }
        )

        return {"ok": True, "status": "verified", "connection_id": conn["id"]}

    def list_contacts(self, *, user: str) -> list[dict[str, Any]]:
        me = self._resolve_user(user)
        my_profile = self._profile_for_email(me["email"])

        contacts: list[dict[str, Any]] = []
        for conn in self._load_connections():
            if conn.get("status") != "verified":
                continue

            requester_email = conn.get("requester_email")
            recipient_email = conn.get("recipient_email")
            if me["email"] not in {requester_email, recipient_email}:
                continue

            other_email = recipient_email if requester_email == me["email"] else requester_email
            other_id = conn.get("recipient_id") if requester_email == me["email"] else conn.get("requester_id")
            other_account = self._resolve_user(other_email)
            other_profile = self._profile_for_email(other_email)

            other_x = conn.get("recipient_x25519_public_key") if requester_email == me["email"] else conn.get("requester_x25519_public_key")
            other_ed = conn.get("recipient_ed25519_public_key") if requester_email == me["email"] else conn.get("requester_ed25519_public_key")
            other_fp = conn.get("recipient_key_fingerprint") if requester_email == me["email"] else conn.get("requester_key_fingerprint")

            my_x_snapshot = conn.get("requester_x25519_public_key") if requester_email == me["email"] else conn.get("recipient_x25519_public_key")
            my_ed_snapshot = conn.get("requester_ed25519_public_key") if requester_email == me["email"] else conn.get("recipient_ed25519_public_key")

            key_changed = (
                (my_profile.get("x25519") or {}).get("public_key") != my_x_snapshot
                or (my_profile.get("ed25519") or {}).get("public_key") != my_ed_snapshot
                or (other_profile.get("x25519") or {}).get("public_key") != other_x
                or (other_profile.get("ed25519") or {}).get("public_key") != other_ed
            )

            contacts.append(
                {
                    "connection_id": conn.get("id"),
                    "user_id": other_id or other_email,
                    "email": other_email,
                    "display_name": other_account.get("display_name") or other_email,
                    "x25519_public_key": other_x,
                    "ed25519_public_key": other_ed,
                    "key_fingerprint": other_fp,
                    "verified_at": conn.get("verified_at"),
                    "trusted": not key_changed,
                    "key_changed": key_changed,
                }
            )

        return contacts

    def get_verified_connection(self, user_a: str, user_b: str) -> dict[str, Any] | None:
        a = self._resolve_user(user_a)
        b = self._resolve_user(user_b)
        conn = self._find_pair(self._load_connections(), a["email"], b["email"])
        if not conn or conn.get("status") != "verified":
            return None

        # If key snapshot no longer matches current keys, require re-verification.
        a_profile = self._profile_for_email(a["email"])
        b_profile = self._profile_for_email(b["email"])
        keys_ok = self._keys_match_snapshot(conn, a["email"], a_profile) and self._keys_match_snapshot(conn, b["email"], b_profile)
        if not keys_ok:
            return None

        return conn

    def get_connection_status(self, *, user: str, peer: str) -> dict[str, Any]:
        user_norm = user.strip().lower()
        peer_norm = peer.strip().lower()
        user_info = self._resolve_user_soft(user_norm)
        if not user_info:
            return {
                "ok": True,
                "user": {"email": user_norm, "display_name": user_norm, "user_id": user_norm},
                "peer": {
                    "email": peer_norm,
                    "display_name": peer_norm,
                    "user_id": peer_norm,
                    "account_exists": False,
                    "verified": False,
                    "profile_exists": False,
                    "has_x25519_public_key": False,
                    "has_ed25519_public_key": False,
                },
                "connection": {
                    "exists": False,
                    "id": None,
                    "status": "none",
                    "requester_email": None,
                    "recipient_email": None,
                    "trusted": False,
                    "verified_at": None,
                },
                "can_send_encrypted": False,
                "reason": "peer_not_found",
            }

        peer_info = self._resolve_user_soft(peer_norm)
        if not peer_info:
            return self._status_payload(user_info, None, None, "peer_not_found")

        if user_info["email"] == peer_info["email"]:
            return self._status_payload(user_info, peer_info, None, "missing_connection")

        accounts = self.auth_service._load_accounts()
        peer_account = self.auth_service._find_account(accounts, peer_info["email"])
        peer_verified = bool(peer_account and peer_account.get("verified"))

        peer_profile = self._profile_for_email(peer_info["email"]) if peer_verified else {}
        profile_exists = bool(peer_profile)
        has_x = bool((peer_profile.get("x25519") or {}).get("public_key"))
        has_ed = bool((peer_profile.get("ed25519") or {}).get("public_key"))

        conn = self._find_pair(self._load_connections(), user_info["email"], peer_info["email"])
        conn_status = str(conn.get("status") or "none") if conn else "none"
        trusted = bool(conn and conn_status == "verified")

        if not peer_verified:
            reason = "peer_not_verified"
        elif not (profile_exists and has_x and has_ed):
            reason = "missing_crypto_profile"
        elif not conn:
            reason = "missing_connection"
        elif conn_status != "verified":
            reason = "pending_connection"
        else:
            reason = "verified_connection"

        can_send = reason == "verified_connection"
        return self._status_payload(user_info, peer_info, conn, reason, can_send_override=can_send, peer_profile=peer_profile, peer_verified=peer_verified, trusted=trusted)

    def _keys_match_snapshot(self, conn: dict[str, Any], email: str, profile: dict[str, Any]) -> bool:
        if conn.get("requester_email") == email:
            x = conn.get("requester_x25519_public_key")
            ed = conn.get("requester_ed25519_public_key")
        else:
            x = conn.get("recipient_x25519_public_key")
            ed = conn.get("recipient_ed25519_public_key")
        return x == (profile.get("x25519") or {}).get("public_key") and ed == (profile.get("ed25519") or {}).get("public_key")

    def resolve_trusted_contact_public_keys(self, *, owner: str, peer: str) -> dict[str, Any]:
        conn = self.get_verified_connection(owner, peer)
        if not conn:
            raise ValueError("Trusted verified connection not found")

        owner_user = self._resolve_user(owner)
        peer_user = self._resolve_user(peer)

        if conn.get("requester_email") == owner_user["email"]:
            return {
                "peer_email": peer_user["email"],
                "peer_user_id": peer_user["user_id"],
                "x25519_public_key": conn.get("recipient_x25519_public_key"),
                "ed25519_public_key": conn.get("recipient_ed25519_public_key"),
                "x25519_fingerprint": CryptoService.fingerprint_public_key(conn.get("recipient_x25519_public_key")),
                "ed25519_fingerprint": CryptoService.fingerprint_public_key(conn.get("recipient_ed25519_public_key")),
                "trusted": True,
            }

        return {
            "peer_email": peer_user["email"],
            "peer_user_id": peer_user["user_id"],
            "x25519_public_key": conn.get("requester_x25519_public_key"),
            "ed25519_public_key": conn.get("requester_ed25519_public_key"),
            "x25519_fingerprint": CryptoService.fingerprint_public_key(conn.get("requester_x25519_public_key")),
            "ed25519_fingerprint": CryptoService.fingerprint_public_key(conn.get("requester_ed25519_public_key")),
            "trusted": True,
        }

    def _resolve_user(self, identifier: str) -> dict[str, Any]:
        normalized = identifier.strip().lower()
        accounts = self.auth_service._load_accounts()
        for account in accounts:
            email = str(account.get("email") or "").strip().lower()
            user_id = str(account.get("user_id") or email).strip().lower()
            if normalized in {email, user_id}:
                if "user_id" not in account:
                    account["user_id"] = user_id
                    self.auth_service._save_accounts(accounts)
                return {
                    "user_id": user_id,
                    "email": email,
                    "display_name": account.get("display_name") or email,
                }
        raise ValueError("User not found")

    def _resolve_user_soft(self, identifier: str) -> dict[str, Any] | None:
        normalized = identifier.strip().lower()
        accounts = self.auth_service._load_accounts()
        for account in accounts:
            email = str(account.get("email") or "").strip().lower()
            user_id = str(account.get("user_id") or email).strip().lower()
            if normalized in {email, user_id}:
                return {
                    "user_id": user_id,
                    "email": email,
                    "display_name": account.get("display_name") or email,
                    "verified": bool(account.get("verified")),
                }
        return None

    def _profile_for_email(self, email: str) -> dict[str, Any]:
        return self.auth_service._ensure_profile_exists(email.strip().lower(), email.strip().lower())

    def _refresh_key_snapshot(
        self,
        conn: dict[str, Any],
        requester: dict[str, Any],
        recipient: dict[str, Any],
        requester_profile: dict[str, Any],
        recipient_profile: dict[str, Any],
    ) -> None:
        requester_x = (requester_profile.get("x25519") or {}).get("public_key")
        requester_ed = (requester_profile.get("ed25519") or {}).get("public_key")
        recipient_x = (recipient_profile.get("x25519") or {}).get("public_key")
        recipient_ed = (recipient_profile.get("ed25519") or {}).get("public_key")

        conn["requester_id"] = requester["user_id"]
        conn["requester_email"] = requester["email"]
        conn["recipient_id"] = recipient["user_id"]
        conn["recipient_email"] = recipient["email"]
        conn["requester_x25519_public_key"] = requester_x
        conn["requester_ed25519_public_key"] = requester_ed
        conn["recipient_x25519_public_key"] = recipient_x
        conn["recipient_ed25519_public_key"] = recipient_ed
        conn["requester_key_fingerprint"] = CryptoService.fingerprint_public_key(requester_ed)
        conn["recipient_key_fingerprint"] = CryptoService.fingerprint_public_key(recipient_ed)

    def _build_connection_json(
        self,
        *,
        requester: dict[str, Any],
        recipient: dict[str, Any],
        requester_profile: dict[str, Any],
        recipient_profile: dict[str, Any],
        verified_at: str | None,
        trusted: bool,
    ) -> dict[str, Any]:
        requester_x = (requester_profile.get("x25519") or {}).get("public_key")
        requester_ed = (requester_profile.get("ed25519") or {}).get("public_key")
        recipient_x = (recipient_profile.get("x25519") or {}).get("public_key")
        recipient_ed = (recipient_profile.get("ed25519") or {}).get("public_key")
        return {
            "requester": {
                "email": requester["email"],
                "display_name": requester.get("display_name") or requester["email"],
                "user_id": requester["user_id"],
                "x25519_public_key": requester_x,
                "ed25519_public_key": requester_ed,
                "x25519_fingerprint": CryptoService.fingerprint_public_key(requester_x),
                "ed25519_fingerprint": CryptoService.fingerprint_public_key(requester_ed),
            },
            "recipient": {
                "email": recipient["email"],
                "display_name": recipient.get("display_name") or recipient["email"],
                "user_id": recipient["user_id"],
                "x25519_public_key": recipient_x,
                "ed25519_public_key": recipient_ed,
                "x25519_fingerprint": CryptoService.fingerprint_public_key(recipient_x),
                "ed25519_fingerprint": CryptoService.fingerprint_public_key(recipient_ed),
            },
            "verified_at": verified_at,
            "trusted": trusted,
        }

    def _status_payload(
        self,
        user_info: dict[str, Any],
        peer_info: dict[str, Any] | None,
        conn: dict[str, Any] | None,
        reason: str,
        *,
        can_send_override: bool | None = None,
        peer_profile: dict[str, Any] | None = None,
        peer_verified: bool | None = None,
        trusted: bool = False,
    ) -> dict[str, Any]:
        profile = peer_profile or {}
        has_x = bool((profile.get("x25519") or {}).get("public_key"))
        has_ed = bool((profile.get("ed25519") or {}).get("public_key"))
        can_send = can_send_override if can_send_override is not None else reason == "verified_connection"
        return {
            "ok": True,
            "user": {
                "email": user_info.get("email"),
                "display_name": user_info.get("display_name"),
                "user_id": user_info.get("user_id"),
            },
            "peer": {
                "email": peer_info.get("email") if peer_info else None,
                "display_name": peer_info.get("display_name") if peer_info else None,
                "user_id": peer_info.get("user_id") if peer_info else None,
                "account_exists": bool(peer_info),
                "verified": bool(peer_verified) if peer_verified is not None else bool(peer_info and peer_info.get("verified")),
                "profile_exists": bool(profile) if peer_info else False,
                "has_x25519_public_key": has_x if peer_info else False,
                "has_ed25519_public_key": has_ed if peer_info else False,
            },
            "connection": {
                "exists": bool(conn),
                "id": conn.get("id") if conn else None,
                "status": str(conn.get("status") or "none") if conn else "none",
                "requester_email": conn.get("requester_email") if conn else None,
                "recipient_email": conn.get("recipient_email") if conn else None,
                "trusted": trusted,
                "verified_at": conn.get("verified_at") if conn else None,
            },
            "can_send_encrypted": can_send,
            "reason": reason,
        }

    def _find_pair(self, connections: list[dict[str, Any]], a_email: str, b_email: str) -> dict[str, Any] | None:
        pair = {a_email, b_email}
        for conn in connections:
            if {conn.get("requester_email"), conn.get("recipient_email")} == pair:
                return conn
        return None

    def _load_connections(self) -> list[dict[str, Any]]:
        rows = self.storage.list_connections()
        return [row for row in rows if isinstance(row, dict)]

    def _save_connections(self, rows: list[dict[str, Any]]) -> None:
        self.storage.replace_connections(rows)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _iso_now_plus(*, minutes: int) -> str:
        return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()

    @staticmethod
    def _generate_code() -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    def _hash_code(self, code: str) -> str:
        digest = hmac.new(self.code_pepper, code.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"hmac-sha256${digest}"

    def _validate_code(self, expected_hash: Any, expires_at: Any, provided_code: str) -> None:
        if not expected_hash or not expires_at:
            raise ValueError("Verification code is missing")

        exp = datetime.fromisoformat(str(expires_at))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) > exp:
            raise ValueError("Verification code has expired")

        provided_hash = self._hash_code(provided_code)
        if not hmac.compare_digest(str(expected_hash), provided_hash):
            raise ValueError("Invalid verification code")

    def _send_connection_email(self, recipient_email: str, requester_email: str, code: str) -> bool:
        try:
            return self.email_service.send_code_email(
                to_email=recipient_email,
                subject="Secure Messenger connection verification",
                code=code,
                purpose=f"Connection request from {requester_email}",
            )
        except Exception:
            return False

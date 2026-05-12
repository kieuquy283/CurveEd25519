from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.profiles.profile_service import ProfileService
from app.services.email_service import EmailService


def _log(message: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[auth][{ts}] {message}")


@dataclass
class AuthResult:
    ok: bool
    message: str
    dev_code: str | None = None
    email_sent: bool = False
    error: str | None = None


class AuthService:
    def __init__(
        self,
        *,
        accounts_path: str = "data/accounts.json",
        profiles_dir: str = "data/profiles",
    ) -> None:
        self.accounts_path = Path(accounts_path)
        self.accounts_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.accounts_path.exists():
            self.accounts_path.write_text("[]", encoding="utf-8")

        self.profile_service = ProfileService(profiles_dir=profiles_dir)
        self.email_service = EmailService()

        env = (os.getenv("APP_ENV") or os.getenv("ENV") or os.getenv("PYTHON_ENV") or "development").lower()
        self.app_env = env
        self.is_development = env in {"dev", "development", "local", "test"}
        self.code_pepper = (os.getenv("AUTH_CODE_PEPPER") or "curveapp-local-pepper").encode("utf-8")

    def register(self, *, email: str, display_name: str, password: str) -> AuthResult:
        normalized_email = self._normalize_email(email)
        self._validate_email(normalized_email)
        self._validate_password(password)

        accounts = self._load_accounts()
        account = self._find_account(accounts, normalized_email)
        now = self._utc_now()

        if account and account.get("verified"):
            raise ValueError("Account already exists")

        profile = self.profile_service.find_by_username(normalized_email)
        if profile is None:
            profile = self.profile_service.create_profile(
                username=normalized_email,
                display_name=display_name.strip() or normalized_email,
                save=True,
            )

        code = self._generate_code()
        code_hash = self._hash_code(code)
        expires = self._iso_now_plus(minutes=10)

        if account is None:
            account = {
                "user_id": normalized_email,
                "email": normalized_email,
                "display_name": display_name.strip() or normalized_email,
                "password_hash": self._hash_password(password),
                "verified": False,
                "created_at": now,
                "updated_at": now,
                "verification_code_hash": code_hash,
                "verification_expires_at": expires,
                "reset_code_hash": None,
                "reset_expires_at": None,
                "profile_id": profile.get("profile_id"),
            }
            accounts.append(account)
        else:
            account["user_id"] = str(account.get("user_id") or normalized_email).strip().lower()
            account["display_name"] = display_name.strip() or account.get("display_name") or normalized_email
            account["password_hash"] = self._hash_password(password)
            account["verification_code_hash"] = code_hash
            account["verification_expires_at"] = expires
            account["reset_code_hash"] = None
            account["reset_expires_at"] = None
            account["profile_id"] = account.get("profile_id") or profile.get("profile_id")
            account["updated_at"] = now

        self._save_accounts(accounts)

        _log(f"register: send verification called for email={normalized_email}")
        sent = self._send_verification_email(normalized_email, code)

        if sent:
            return AuthResult(
                ok=True,
                message="Verification code sent to your email.",
                email_sent=True,
            )

        smtp_error = self.email_service.last_error or "SMTP send failed"
        _log(f"register: verification email failed for email={normalized_email}: {smtp_error}")

        if self.is_development:
            return AuthResult(
                ok=True,
                message="SMTP unavailable. Development fallback enabled.",
                dev_code=code,
                email_sent=False,
                error=f"{self.email_service.last_error_class or 'SMTPError'}: {smtp_error}",
            )

        return AuthResult(
            ok=False,
            message="Account created but verification email could not be sent. Please retry later.",
            email_sent=False,
            error=f"{self.email_service.last_error_class or 'SMTPError'}: {smtp_error}",
        )

    def login(self, *, email: str, password: str) -> dict[str, Any]:
        normalized_email = self._normalize_email(email)
        accounts = self._load_accounts()
        account = self._find_account(accounts, normalized_email)

        if not account:
            raise ValueError("Invalid email or password")

        if not self._verify_password(password, str(account.get("password_hash") or "")):
            raise ValueError("Invalid email or password")

        if not account.get("verified"):
            raise PermissionError("Account is not verified. Please verify your email first.")

        account["updated_at"] = self._utc_now()
        self._save_accounts(accounts)

        profile = self._profile_for_account(account)

        return {
            "user": {
                "id": str(account.get("user_id") or normalized_email),
                "email": normalized_email,
                "displayName": account.get("display_name") or normalized_email,
            },
            "profile": {
                "profile_id": profile.get("profile_id"),
                "username": profile.get("username"),
                "display_name": profile.get("display_name"),
                "ed25519_public_key": (profile.get("ed25519") or {}).get("public_key"),
                "x25519_public_key": (profile.get("x25519") or {}).get("public_key"),
            },
        }

    def verify_email(self, *, email: str, code: str) -> None:
        normalized_email = self._normalize_email(email)
        accounts = self._load_accounts()
        account = self._require_account(accounts, normalized_email)

        if account.get("verified"):
            return

        self._validate_code(account.get("verification_code_hash"), account.get("verification_expires_at"), code)

        account["verified"] = True
        account["verification_code_hash"] = None
        account["verification_expires_at"] = None
        account["updated_at"] = self._utc_now()
        self._save_accounts(accounts)

    def resend_verification(self, *, email: str) -> AuthResult:
        normalized_email = self._normalize_email(email)
        accounts = self._load_accounts()
        account = self._require_account(accounts, normalized_email)

        if account.get("verified"):
            raise ValueError("Account is already verified")

        code = self._generate_code()
        account["verification_code_hash"] = self._hash_code(code)
        account["verification_expires_at"] = self._iso_now_plus(minutes=10)
        account["updated_at"] = self._utc_now()
        self._save_accounts(accounts)

        _log(f"resend_verification: send verification called for email={normalized_email}")
        sent = self._send_verification_email(normalized_email, code)

        if sent:
            return AuthResult(
                ok=True,
                message="Verification code sent to your email.",
                email_sent=True,
            )

        smtp_error = self.email_service.last_error or "SMTP send failed"
        _log(f"resend_verification: verification email failed for email={normalized_email}: {smtp_error}")

        if self.is_development:
            return AuthResult(
                ok=True,
                message="SMTP unavailable. Development fallback enabled.",
                dev_code=code,
                email_sent=False,
                error=f"{self.email_service.last_error_class or 'SMTPError'}: {smtp_error}",
            )

        return AuthResult(
            ok=False,
            message="Could not send verification email. Please retry later.",
            email_sent=False,
            error=f"{self.email_service.last_error_class or 'SMTPError'}: {smtp_error}",
        )

    def request_password_reset(self, *, email: str) -> AuthResult:
        normalized_email = self._normalize_email(email)
        accounts = self._load_accounts()
        account = self._find_account(accounts, normalized_email)

        generic = AuthResult(ok=True, message="If the account exists, a reset code has been sent.", email_sent=False)
        if not account:
            return generic

        code = self._generate_code()
        account["reset_code_hash"] = self._hash_code(code)
        account["reset_expires_at"] = self._iso_now_plus(minutes=10)
        account["updated_at"] = self._utc_now()
        self._save_accounts(accounts)

        sent = self._send_reset_email(normalized_email, code)
        if not sent:
            _log(f"request_password_reset: reset email failed for email={normalized_email}: {self.email_service.last_error or 'SMTP send failed'}")

        if sent:
            generic.email_sent = True
            return generic

        smtp_error = self.email_service.last_error or "SMTP send failed"
        if self.is_development:
            generic.dev_code = code
            generic.error = f"{self.email_service.last_error_class or 'SMTPError'}: {smtp_error}"
            return generic

        return AuthResult(
            ok=False,
            message="Could not send password reset email. Please retry later.",
            email_sent=False,
            error=f"{self.email_service.last_error_class or 'SMTPError'}: {smtp_error}",
        )

    def reset_password(self, *, email: str, code: str, new_password: str) -> None:
        normalized_email = self._normalize_email(email)
        self._validate_password(new_password)

        accounts = self._load_accounts()
        account = self._require_account(accounts, normalized_email)

        self._validate_code(account.get("reset_code_hash"), account.get("reset_expires_at"), code)

        account["password_hash"] = self._hash_password(new_password)
        account["reset_code_hash"] = None
        account["reset_expires_at"] = None
        account["updated_at"] = self._utc_now()
        self._save_accounts(accounts)

    def get_email_config_status(self) -> dict[str, object]:
        status = self.email_service.config_status()
        return {
            "ok": True,
            "app_env": status["app_env"],
            "smtp_host": status["smtp_host"],
            "smtp_port": status["smtp_port"],
            "smtp_from": status["smtp_from"],
            "has_username": status["has_username"],
            "has_password": status["has_password"],
            "use_tls": status["smtp_use_tls"],
        }

    def send_test_email(self, to: str) -> tuple[bool, str | None]:
        code = "000000"
        sent = self.email_service.send_code_email(
            to_email=to,
            subject="Secure Messenger test email",
            code=code,
            purpose="Email service test",
        )
        if sent:
            return True, None
        err = self.email_service.last_error or "SMTP send failed"
        cls = self.email_service.last_error_class or "SMTPError"
        return False, f"{cls}: {err}"

    def _profile_for_account(self, account: dict[str, Any]) -> dict[str, Any]:
        profile_id = str(account.get("profile_id") or "").strip()
        if profile_id:
            try:
                return self.profile_service.load_profile(profile_id)
            except Exception:
                pass

        email = str(account.get("email") or "").strip().lower()
        profile = self.profile_service.find_by_username(email)
        if profile:
            account["profile_id"] = profile.get("profile_id")
            return profile

        profile = self.profile_service.create_profile(
            username=email,
            display_name=account.get("display_name") or email,
            save=True,
        )
        account["profile_id"] = profile.get("profile_id")
        return profile

    def _load_accounts(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.accounts_path.read_text(encoding="utf-8"))
        except Exception:
            data = []
        if not isinstance(data, list):
            return []
        return [row for row in data if isinstance(row, dict)]

    def _save_accounts(self, accounts: list[dict[str, Any]]) -> None:
        self.accounts_path.write_text(json.dumps(accounts, indent=2), encoding="utf-8")

    def _find_account(self, accounts: list[dict[str, Any]], email: str) -> dict[str, Any] | None:
        for account in accounts:
            if str(account.get("email") or "").strip().lower() == email:
                return account
        return None

    def _require_account(self, accounts: list[dict[str, Any]], email: str) -> dict[str, Any]:
        account = self._find_account(accounts, email)
        if not account:
            raise ValueError("Account not found")
        return account

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _validate_email(email: str) -> None:
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("Invalid email format")

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")

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

        try:
            exp = datetime.fromisoformat(str(expires_at))
        except Exception as exc:
            raise ValueError("Verification code is invalid") from exc

        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) > exp:
            raise ValueError("Verification code has expired")

        provided_hash = self._hash_code(provided_code)
        if not hmac.compare_digest(str(expected_hash), provided_hash):
            raise ValueError("Invalid verification code")

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        n = 2**14
        r = 8
        p = 1
        key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32)
        return "scrypt${}${}${}${}${}".format(
            n,
            r,
            p,
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(key).decode("ascii"),
        )

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        try:
            prefix, n_str, r_str, p_str, salt_b64, key_b64 = password_hash.split("$", 5)
            if prefix != "scrypt":
                return False
            salt = base64.b64decode(salt_b64.encode("ascii"))
            expected = base64.b64decode(key_b64.encode("ascii"))
            derived = hashlib.scrypt(
                password.encode("utf-8"),
                salt=salt,
                n=int(n_str),
                r=int(r_str),
                p=int(p_str),
                dklen=len(expected),
            )
            return hmac.compare_digest(derived, expected)
        except Exception:
            return False

    def _send_verification_email(self, email: str, code: str) -> bool:
        return self.email_service.send_code_email(
            to_email=email,
            subject="Secure Messenger verification code",
            code=code,
            purpose="Email verification",
        )

    def _send_reset_email(self, email: str, code: str) -> bool:
        return self.email_service.send_code_email(
            to_email=email,
            subject="Secure Messenger password reset code",
            code=code,
            purpose="Password reset",
        )

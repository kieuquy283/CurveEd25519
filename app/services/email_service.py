from __future__ import annotations

import os
import smtplib
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from email.message import EmailMessage


def _log(message: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[email][{ts}] {message}")


class EmailService:
    def __init__(self) -> None:
        self.provider = (os.getenv("EMAIL_PROVIDER") or "smtp").strip().lower()
        self.resend_api_key = (os.getenv("RESEND_API_KEY") or "").strip()
        self.brevo_api_key = (os.getenv("BREVO_API_KEY") or "").strip()
        self.email_from = (os.getenv("EMAIL_FROM") or "").strip()
        self.email_from_name = (os.getenv("EMAIL_FROM_NAME") or "").strip()

        self.host = (os.getenv("SMTP_HOST") or "").strip()
        raw_port = (os.getenv("SMTP_PORT") or "0").strip()
        try:
            self.port = int(raw_port or 0)
        except ValueError:
            self.port = 0
        self.username = (os.getenv("SMTP_USERNAME") or "").strip()
        self.password = (os.getenv("SMTP_PASSWORD") or "").strip()
        self.sender = (os.getenv("SMTP_FROM") or "").strip()
        self.use_tls = (os.getenv("SMTP_USE_TLS") or "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.app_env = (
            os.getenv("APP_ENV")
            or os.getenv("ENV")
            or os.getenv("PYTHON_ENV")
            or "development"
        ).strip().lower()
        self.is_development = self.app_env in {"dev", "development", "local", "test"}
        self.last_error: str | None = None
        self.last_error_class: str | None = None

    def is_configured(self) -> bool:
        if self.provider == "brevo":
            return bool(self.brevo_api_key and self.email_from)
        if self.provider == "resend":
            return bool(self.resend_api_key and self.email_from)
        return bool(
            self.host
            and self.port
            and self.sender
            and self.username
            and self.password
        )

    def config_status(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "email_from": self.email_from or self.sender or "",
            "email_from_name": self.email_from_name or "CurveEd25519",
            "has_brevo_api_key": bool(self.brevo_api_key),
            "has_resend_api_key": bool(self.resend_api_key),
            "smtp_host": self.host or "",
            "smtp_port": self.port,
            "smtp_from": self.sender or "",
            "has_username": bool(self.username),
            "has_password": bool(self.password),
            "smtp_use_tls": self.use_tls,
            "app_env": self.app_env,
            "configured": self.is_configured(),
        }

    def send_code_email(self, *, to_email: str, subject: str, code: str, purpose: str) -> bool:
        self.last_error = None
        self.last_error_class = None
        status = self.config_status()
        _log(
            "send_code_email requested "
            f"provider={status['provider']} email_from={status['email_from']} "
            f"email_from_name={status['email_from_name']} has_brevo_api_key={status['has_brevo_api_key']} "
            f"has_resend_api_key={status['has_resend_api_key']} "
            f"host={status['smtp_host']} port={status['smtp_port']} from={status['smtp_from']} "
            f"has_username={status['has_username']} has_password={status['has_password']} tls={status['smtp_use_tls']}"
        )

        if not self.is_configured():
            if self.provider == "brevo":
                self.last_error = "BREVO_API_KEY is missing"
                self.last_error_class = "BrevoConfigurationError"
                _log("send_code_email skipped: Brevo is not fully configured")
            elif self.provider == "resend":
                self.last_error = "Resend is not fully configured"
                self.last_error_class = "ResendConfigurationError"
                _log("send_code_email skipped: Resend is not fully configured")
            else:
                self.last_error = "SMTP is not fully configured"
                self.last_error_class = "SMTPConfigurationError"
                _log("send_code_email skipped: SMTP is not fully configured")
            return False

        body_lines = [
            "Secure Messenger verification",
            "",
            f"Purpose: {purpose}",
            f"Code: {code}",
            "",
            "If you did not request this, ignore this email.",
        ]
        body_text = "\n".join(body_lines)

        if self.provider == "resend":
            return self._send_via_resend(
                to_email=to_email,
                subject=subject,
                body_text=body_text,
            )
        if self.provider == "brevo":
            return self._send_via_brevo(
                to_email=to_email,
                subject=subject,
                body_text=body_text,
            )

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = to_email
        msg.set_content(body_text)

        try:
            if self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, timeout=20) as smtp:
                    smtp.ehlo()
                    smtp.login(self.username, self.password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
                    smtp.ehlo()
                    if self.use_tls:
                        smtp.starttls()
                        smtp.ehlo()
                    smtp.login(self.username, self.password)
                    smtp.send_message(msg)
            _log(f"send_code_email success to={to_email} subject={subject}")
            return True
        except Exception as exc:
            self.last_error_class = exc.__class__.__name__
            self.last_error = str(exc)
            _log(
                f"send_code_email failed to={to_email} subject={subject} "
                f"error_class={self.last_error_class} error={self.last_error}"
            )
            return False

    def _send_via_brevo(self, *, to_email: str, subject: str, body_text: str) -> bool:
        _log(
            "brevo send attempt "
            f"provider={self.provider} email_from={self.email_from} recipient={to_email} "
            f"has_brevo_api_key={bool(self.brevo_api_key)}"
        )
        if not self.brevo_api_key:
            self.last_error_class = "BrevoConfigurationError"
            self.last_error = "BREVO_API_KEY is missing"
            return False

        html_body = (
            "<p>Secure Messenger verification</p>"
            f"<p><strong>Code:</strong> {body_text.splitlines()[3] if len(body_text.splitlines()) > 3 else ''}</p>"
            "<p>If you did not request this, ignore this email.</p>"
        )
        payload = {
            "sender": {
                "name": self.email_from_name or "CurveEd25519",
                "email": self.email_from,
            },
            "to": [{"email": to_email}],
            "subject": subject,
            "textContent": body_text,
            "htmlContent": html_body,
        }
        req = urllib.request.Request(
            url="https://api.brevo.com/v3/smtp/email",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "api-key": self.brevo_api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "CurveEd25519/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                status_code = int(getattr(resp, "status", 0))
                if status_code < 200 or status_code >= 300:
                    body = resp.read().decode("utf-8", errors="replace")
                    self.last_error_class = "BrevoHTTPError"
                    self.last_error = f"HTTP {status_code}: {body or 'Unexpected response'}"
                    _log(f"brevo response status={status_code} recipient={to_email} body={body or '<empty>'}")
                    return False
                _log(f"brevo response status={status_code} recipient={to_email}")
            _log(f"send_code_email success to={to_email} subject={subject}")
            return True
        except urllib.error.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                error_body = ""
            self.last_error_class = "BrevoHTTPError"
            self.last_error = f"HTTP {exc.code}: {exc.reason} - {error_body or '<empty>'}"
            _log(f"brevo response status={exc.code} recipient={to_email} body={error_body or '<empty>'}")
            return False
        except Exception as exc:
            self.last_error_class = exc.__class__.__name__
            self.last_error = str(exc)
            _log(
                f"send_code_email failed to={to_email} subject={subject} "
                f"error_class={self.last_error_class} error={self.last_error}"
            )
            return False

    def _send_via_resend(self, *, to_email: str, subject: str, body_text: str) -> bool:
        _log(
            "resend send attempt "
            f"provider={self.provider} email_from={self.email_from} recipient={to_email} "
            f"has_resend_api_key={bool(self.resend_api_key)}"
        )
        payload = {
            "from": self.email_from,
            "to": [to_email],
            "subject": subject,
            "text": body_text,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url="https://api.resend.com/emails",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json",
                "User-Agent": "CurveEd25519/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                status_code = getattr(resp, "status", 0)
                _log(f"resend response status={status_code} recipient={to_email}")
                if int(status_code) < 200 or int(status_code) >= 300:
                    self.last_error_class = "ResendHTTPError"
                    self.last_error = f"Unexpected status {status_code}"
                    _log(
                        f"send_code_email failed to={to_email} subject={subject} "
                        f"error_class={self.last_error_class} error={self.last_error}"
                    )
                    return False
            _log(f"send_code_email success to={to_email} subject={subject}")
            return True
        except urllib.error.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                error_body = ""
            self.last_error_class = "ResendHTTPError"
            if error_body:
                self.last_error = f"HTTP {exc.code}: {exc.reason} - {error_body}"
            else:
                self.last_error = f"HTTP {exc.code}: {exc.reason}"
            _log(
                f"resend response status={exc.code} recipient={to_email} body={error_body or '<empty>'}"
            )
            _log(
                f"send_code_email failed to={to_email} subject={subject} "
                f"error_class={self.last_error_class} error={self.last_error}"
            )
            return False
        except Exception as exc:
            self.last_error_class = exc.__class__.__name__
            self.last_error = str(exc)
            _log(
                f"send_code_email failed to={to_email} subject={subject} "
                f"error_class={self.last_error_class} error={self.last_error}"
            )
            return False

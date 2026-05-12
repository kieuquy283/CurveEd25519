from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


class EmailService:
    def __init__(self) -> None:
        self.host = (os.getenv("SMTP_HOST") or "").strip()
        self.port = int((os.getenv("SMTP_PORT") or "0").strip() or 0)
        self.username = (os.getenv("SMTP_USERNAME") or "").strip()
        self.password = (os.getenv("SMTP_PASSWORD") or "").strip()
        self.sender = (os.getenv("SMTP_FROM") or "").strip()
        self.use_tls = (os.getenv("SMTP_USE_TLS") or "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def is_configured(self) -> bool:
        return bool(self.host and self.port and self.sender)

    def send_code_email(self, *, to_email: str, subject: str, code: str, purpose: str) -> bool:
        if not self.is_configured():
            return False

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = to_email
        msg.set_content(
            "\n".join(
                [
                    "Secure Messenger verification",
                    "",
                    f"Purpose: {purpose}",
                    f"Code: {code}",
                    "",
                    "If you did not request this, ignore this email.",
                ]
            )
        )

        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            if self.use_tls:
                smtp.starttls()
            if self.username:
                smtp.login(self.username, self.password)
            smtp.send_message(msg)

        return True

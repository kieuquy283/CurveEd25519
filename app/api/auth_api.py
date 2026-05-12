from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from pathlib import Path
import os

from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "profiles").mkdir(parents=True, exist_ok=True)
service = AuthService(
    accounts_path=str(DATA_DIR / "accounts.json"),
    profiles_dir=str(DATA_DIR / "profiles"),
)


def _log(message: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[auth_api][{ts}] {message}")


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    display_name: str
    password: str


class VerifyEmailRequest(BaseModel):
    email: str
    code: str


class ResendVerificationRequest(BaseModel):
    email: str


class RequestPasswordResetRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


class TestEmailRequest(BaseModel):
    to: str


class UpdateProfileRequest(BaseModel):
    email: str
    display_name: str


class ChangePasswordRequest(BaseModel):
    email: str
    current_password: str
    new_password: str


class DeleteAccountRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(req: LoginRequest):
    try:
        result = service.login(email=req.email, password=req.password)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return {
        "ok": True,
        "user": result["user"],
        "profile": result["profile"],
    }


@router.post("/register")
def register(req: RegisterRequest):
    try:
        result = service.register(
            email=req.email,
            display_name=req.display_name,
            password=req.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = {
        "ok": result.ok,
        "requires_verification": True,
        "message": result.message,
        "email_sent": result.email_sent,
    }
    if result.error:
        response["error"] = result.error
    if result.dev_code:
        response["dev_code"] = result.dev_code
    return response


@router.post("/verify-email")
def verify_email(req: VerifyEmailRequest):
    try:
        service.verify_email(email=req.email, code=req.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "message": "Email verified",
    }


@router.post("/resend-verification")
def resend_verification(req: ResendVerificationRequest):
    try:
        result = service.resend_verification(email=req.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = {
        "ok": result.ok,
        "message": result.message,
        "email_sent": result.email_sent,
    }
    if result.error:
        response["error"] = result.error
    if result.dev_code:
        response["dev_code"] = result.dev_code
    return response


@router.post("/request-password-reset")
def request_password_reset(req: RequestPasswordResetRequest):
    result = service.request_password_reset(email=req.email)
    response = {
        "ok": result.ok,
        "message": result.message,
        "email_sent": result.email_sent,
    }
    if result.error:
        response["error"] = result.error
    if result.dev_code:
        response["dev_code"] = result.dev_code
    return response


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    try:
        service.reset_password(
            email=req.email,
            code=req.code,
            new_password=req.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "message": "Password reset successful",
    }


@router.get("/email-config")
def email_config():
    _log("GET /api/auth/email-config")
    return service.get_email_config_status()


@router.post("/test-email")
def test_email(req: TestEmailRequest):
    _log("POST /api/auth/test-email")
    sent, error = service.send_test_email(req.to)
    if sent:
        return {
            "ok": True,
            "sent": True,
            "message": "Test email sent",
        }
    return {
        "ok": False,
        "sent": False,
        "error": error or "Email send failed",
    }


@router.get("/debug-user")
def debug_user(email: str):
    normalized_email = email.strip().lower()
    _log(f"GET /api/auth/debug-user normalized_email={normalized_email}")
    status = service.debug_user_status(normalized_email)
    status["data_dir"] = str(DATA_DIR.resolve())
    status["accounts_path"] = str((DATA_DIR / "accounts.json").resolve())
    status["profiles_dir"] = str((DATA_DIR / "profiles").resolve())
    return status


@router.get("/debug-storage")
def debug_storage():
    _log("GET /api/auth/debug-storage")
    return service.debug_storage_status()


@router.get("/me")
def me(user: str):
    try:
        return service.get_me(email=user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/profile")
def update_profile(req: UpdateProfileRequest):
    try:
        return service.update_profile(email=req.email, display_name=req.display_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/change-password")
def change_password(req: ChangePasswordRequest):
    try:
        return service.change_password(
            email=req.email,
            current_password=req.current_password,
            new_password=req.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/account")
def delete_account(req: DeleteAccountRequest):
    try:
        return service.delete_account(email=req.email, password=req.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

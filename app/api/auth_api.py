from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])
service = AuthService(accounts_path="data/accounts.json", profiles_dir="data/profiles")


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
    return service.get_email_config_status()


@router.post("/test-email")
def test_email(req: TestEmailRequest):
    sent, error = service.send_test_email(req.to)
    return {
        "ok": sent,
        "sent": sent,
        "error": error,
    }

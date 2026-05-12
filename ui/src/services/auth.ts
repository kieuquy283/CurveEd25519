import { getApiBaseUrl } from "@/config/env";

export interface AuthUser {
  id: string;
  email: string;
  displayName: string;
}

interface LoginResponse {
  ok: boolean;
  user: AuthUser;
  profile: Record<string, unknown>;
}

interface RegisterResponse {
  ok: boolean;
  requires_verification: boolean;
  message: string;
  dev_code?: string;
}

interface GenericResponse {
  ok: boolean;
  message: string;
  dev_code?: string;
}

async function postJson<T>(path: string, payload: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : `HTTP ${response.status}`;
    throw new Error(detail);
  }

  return data as T;
}

export async function loginWithEmail(params: { email: string; password: string }): Promise<LoginResponse> {
  return postJson<LoginResponse>("/api/auth/login", params);
}

export async function registerWithEmail(params: {
  email: string;
  display_name: string;
  password: string;
}): Promise<RegisterResponse> {
  return postJson<RegisterResponse>("/api/auth/register", params);
}

export async function verifyEmailCode(params: { email: string; code: string }): Promise<GenericResponse> {
  return postJson<GenericResponse>("/api/auth/verify-email", params);
}

export async function resendVerificationCode(params: { email: string }): Promise<GenericResponse> {
  return postJson<GenericResponse>("/api/auth/resend-verification", params);
}

export async function requestPasswordReset(params: { email: string }): Promise<GenericResponse> {
  return postJson<GenericResponse>("/api/auth/request-password-reset", params);
}

export async function resetPassword(params: {
  email: string;
  code: string;
  new_password: string;
}): Promise<GenericResponse> {
  return postJson<GenericResponse>("/api/auth/reset-password", params);
}

"use client";

import React, { useMemo, useState } from "react";
import { resendVerificationCode } from "@/services/auth";
import { useAuthStore } from "@/store/useAuthStore";

type AuthMode = "login" | "register" | "verify" | "forgot" | "reset";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function AuthScreen() {
  const {
    login,
    register,
    verifyEmail,
    requestPasswordReset,
    resetPassword,
    loading,
    error,
    clearError,
  } = useAuthStore();

  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [message, setMessage] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);

  const normalizedEmail = email.trim().toLowerCase();
  const emailValid = useMemo(() => EMAIL_PATTERN.test(normalizedEmail), [normalizedEmail]);

  const setModeSafe = (next: AuthMode) => {
    clearError();
    setMessage("");
    setDevCode(null);
    setMode(next);
  };

  const onLogin = async () => {
    if (!emailValid) return setMessage("Please enter a valid email.");
    if (!password) return setMessage("Please enter your password.");

    setMessage("");
    try {
      await login(normalizedEmail, password);
    } catch {
      // error is already stored in auth store
    }
  };

  const onRegister = async () => {
    if (!emailValid) return setMessage("Please enter a valid email.");
    if (password.length < 8) return setMessage("Password must be at least 8 characters.");
    if (password !== confirmPassword) return setMessage("Password confirmation does not match.");

    setMessage("");
    try {
      const result = await register(normalizedEmail, displayName.trim() || normalizedEmail, password);
      if (result.dev_code) {
        setDevCode(result.dev_code);
      }
      setMessage("Verification code sent to your email.");
      setMode("verify");
    } catch {
      // error is already stored in auth store
    }
  };

  const onVerify = async () => {
    if (!emailValid) return setMessage("Please enter a valid email.");
    if (!code.trim()) return setMessage("Please enter verification code.");

    setMessage("");
    try {
      await verifyEmail(normalizedEmail, code.trim());
      setMessage("Email verified. You can now log in.");
      setMode("login");
    } catch {
      // error is already stored in auth store
    }
  };

  const onResendVerification = async () => {
    if (!emailValid) return setMessage("Please enter a valid email.");

    setMessage("");
    try {
      const result = await resendVerificationCode({ email: normalizedEmail });
      if (result.dev_code) {
        setDevCode(result.dev_code);
      }
      setMessage("Verification code sent to your email.");
    } catch (resendError) {
      setMessage(resendError instanceof Error ? resendError.message : "Failed to resend verification code.");
    }
  };

  const onRequestReset = async () => {
    if (!emailValid) return setMessage("Please enter a valid email.");

    setMessage("");
    try {
      const result = await requestPasswordReset(normalizedEmail);
      if (result.dev_code) {
        setDevCode(result.dev_code);
      }
      setMessage(result.message || "If the account exists, a reset code has been sent.");
      setMode("reset");
    } catch {
      // error is already stored in auth store
    }
  };

  const onResetPassword = async () => {
    if (!emailValid) return setMessage("Please enter a valid email.");
    if (!code.trim()) return setMessage("Please enter reset code.");
    if (newPassword.length < 8) return setMessage("Password must be at least 8 characters.");
    if (newPassword !== confirmNewPassword) return setMessage("Password confirmation does not match.");

    setMessage("");
    try {
      await resetPassword(normalizedEmail, code.trim(), newPassword);
      setMessage("Password reset successful. You can now log in.");
      setMode("login");
    } catch {
      // error is already stored in auth store
    }
  };

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-black p-4">
      <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
        <h1 className="text-lg font-semibold text-zinc-100">Secure Messenger Login</h1>
        <p className="mt-1 text-xs text-zinc-400">This is a local/demo auth system.</p>

        <div className="mt-4 space-y-3">
          <input
            type="email"
            placeholder="email@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-blue-500"
          />

          {mode === "register" && (
            <input
              type="text"
              placeholder="Display name"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-blue-500"
            />
          )}

          {(mode === "login" || mode === "register") && (
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-blue-500"
            />
          )}

          {mode === "register" && (
            <input
              type="password"
              placeholder="Confirm password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-blue-500"
            />
          )}

          {(mode === "verify" || mode === "reset") && (
            <input
              type="text"
              placeholder="Verification code"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-blue-500"
            />
          )}

          {mode === "reset" && (
            <>
              <p className="text-xs text-zinc-400">Forgot password requires email verification.</p>
              <input
                type="password"
                placeholder="New password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-blue-500"
              />
              <input
                type="password"
                placeholder="Confirm new password"
                value={confirmNewPassword}
                onChange={(event) => setConfirmNewPassword(event.target.value)}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-blue-500"
              />
            </>
          )}
        </div>

        {(error || message) && (
          <div className="mt-3 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-zinc-200">
            {error || message}
          </div>
        )}

        {devCode && (
          <div className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
            Dev code: {devCode}
          </div>
        )}

        <div className="mt-4 flex flex-col gap-2">
          {mode === "login" && (
            <button type="button" onClick={onLogin} disabled={loading} className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500 disabled:opacity-50">
              {loading ? "Logging in..." : "Login"}
            </button>
          )}

          {mode === "register" && (
            <button type="button" onClick={onRegister} disabled={loading} className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500 disabled:opacity-50">
              {loading ? "Registering..." : "Register"}
            </button>
          )}

          {mode === "verify" && (
            <>
              <button type="button" onClick={onVerify} disabled={loading} className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500 disabled:opacity-50">
                {loading ? "Verifying..." : "Verify"}
              </button>
              <button type="button" onClick={onResendVerification} disabled={loading} className="w-full rounded-lg border border-zinc-600 px-4 py-2 text-sm text-zinc-200 hover:border-zinc-400 disabled:opacity-50">
                Resend code
              </button>
            </>
          )}

          {mode === "forgot" && (
            <button type="button" onClick={onRequestReset} disabled={loading} className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500 disabled:opacity-50">
              {loading ? "Sending..." : "Send reset code"}
            </button>
          )}

          {mode === "reset" && (
            <button type="button" onClick={onResetPassword} disabled={loading} className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500 disabled:opacity-50">
              {loading ? "Resetting..." : "Reset password"}
            </button>
          )}
        </div>

        <div className="mt-4 flex flex-wrap gap-3 text-xs text-zinc-400">
          {mode !== "login" && <button type="button" onClick={() => setModeSafe("login")} className="hover:text-zinc-100">Back to login</button>}
          {mode !== "register" && <button type="button" onClick={() => setModeSafe("register")} className="hover:text-zinc-100">Create account</button>}
          {mode !== "forgot" && <button type="button" onClick={() => setModeSafe("forgot")} className="hover:text-zinc-100">Forgot password?</button>}
          {mode !== "verify" && <button type="button" onClick={() => setModeSafe("verify")} className="hover:text-zinc-100">Verify email</button>}
        </div>
      </div>
    </div>
  );
}

"use client";

import React, { useMemo, useState } from "react";
import { Eye, EyeOff, KeyRound, MailCheck, Shield, UserPlus } from "lucide-react";
import { resendVerificationCode } from "@/services/auth";
import { useAuthStore } from "@/store/useAuthStore";
import AuthShell from "@/components/auth/AuthShell";
import AuthCard from "@/components/auth/AuthCard";

type AuthMode = "login" | "register" | "verify" | "forgot" | "reset";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function AuthScreen() {
  const { login, register, verifyEmail, requestPasswordReset, resetPassword, loading, error, clearError } = useAuthStore();

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
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmNewPassword, setShowConfirmNewPassword] = useState(false);

  const normalizedEmail = email.trim().toLowerCase();
  const emailValid = useMemo(() => EMAIL_PATTERN.test(normalizedEmail), [normalizedEmail]);

  const setModeSafe = (next: AuthMode) => {
    clearError();
    setMessage("");
    setDevCode(null);
    setMode(next);
  };

  const onLogin = async () => {
    if (!emailValid) return setMessage("Vui lòng nhập email hợp lệ.");
    if (!password) return setMessage("Vui lòng nhập mật khẩu.");
    setMessage("");
    try {
      await login(normalizedEmail, password);
    } catch {}
  };

  const onRegister = async () => {
    if (!emailValid) return setMessage("Vui lòng nhập email hợp lệ.");
    if (password.length < 8) return setMessage("Mật khẩu phải có ít nhất 8 ký tự.");
    if (password !== confirmPassword) return setMessage("Mật khẩu xác nhận không khớp.");
    setMessage("");
    try {
      const result = await register(normalizedEmail, displayName.trim() || normalizedEmail, password);
      if (result.dev_code) setDevCode(result.dev_code);
      if (result.email_sent) {
        setMessage("Mã xác minh đã được gửi đến email của bạn.");
        setMode("verify");
      } else {
        setMessage(`Không thể gửi email xác minh: ${result.error || result.message}`);
      }
    } catch {}
  };

  const onVerify = async () => {
    if (!emailValid) return setMessage("Vui lòng nhập email hợp lệ.");
    if (!code.trim()) return setMessage("Vui lòng nhập mã xác minh.");
    setMessage("");
    try {
      await verifyEmail(normalizedEmail, code.trim());
      setMessage("Xác minh thành công. Bạn có thể đăng nhập.");
      setMode("login");
    } catch {}
  };

  const onResendVerification = async () => {
    if (!emailValid) return setMessage("Vui lòng nhập email hợp lệ.");
    setMessage("");
    try {
      const result = await resendVerificationCode({ email: normalizedEmail });
      if (result.dev_code) setDevCode(result.dev_code);
      if (result.email_sent === false) setMessage(`Không thể gửi lại mã: ${result.error || result.message}`);
      else setMessage("Mã xác minh đã được gửi lại.");
    } catch (resendError) {
      setMessage(resendError instanceof Error ? resendError.message : "Không thể gửi lại mã xác minh.");
    }
  };

  const onRequestReset = async () => {
    if (!emailValid) return setMessage("Vui lòng nhập email hợp lệ.");
    setMessage("");
    try {
      const result = await requestPasswordReset(normalizedEmail);
      if (result.dev_code) setDevCode(result.dev_code);
      if (result.email_sent === false && result.error) {
        setMessage(`Không thể gửi mã đặt lại: ${result.error}`);
      } else {
        setMessage(result.message || "Mã đặt lại đã được gửi đến email của bạn.");
        setMode("reset");
      }
    } catch {}
  };

  const onResetPassword = async () => {
    if (!emailValid) return setMessage("Vui lòng nhập email hợp lệ.");
    if (!code.trim()) return setMessage("Vui lòng nhập mã đặt lại.");
    if (newPassword.length < 8) return setMessage("Mật khẩu mới phải có ít nhất 8 ký tự.");
    if (newPassword !== confirmNewPassword) return setMessage("Mật khẩu xác nhận không khớp.");
    setMessage("");
    try {
      await resetPassword(normalizedEmail, code.trim(), newPassword);
      setMessage("Đặt lại mật khẩu thành công. Bạn có thể đăng nhập.");
      setMode("login");
    } catch {}
  };

  const title =
    mode === "login"
      ? "Welcome back"
      : mode === "register"
        ? "Create secure account"
        : mode === "verify"
          ? "Verify your email"
          : mode === "forgot"
            ? "Reset access"
            : "Set new password";

  const subtitle =
    mode === "login"
      ? "Log in to continue your secure conversations."
      : mode === "register"
        ? "Start encrypted conversations with verified identity."
        : mode === "verify"
          ? "Enter the code we sent to your inbox."
          : mode === "forgot"
            ? "We will send a verification code to your email."
            : "Choose a strong password to protect your account.";

  return (
    <AuthShell>
      <AuthCard>
        <div className="mb-5">
          <h2 className="text-2xl font-semibold text-white">{title}</h2>
          <p className="mt-1 text-sm text-zinc-300">{subtitle}</p>
        </div>

        <div className="mb-5 grid grid-cols-2 rounded-2xl border border-white/10 bg-white/5 p-1">
          <button
            type="button"
            onClick={() => setModeSafe("login")}
            className={`rounded-xl px-3 py-2 text-sm font-medium transition ${
              mode === "login"
                ? "bg-gradient-to-r from-violet-600/90 to-blue-600/90 text-white shadow-[0_0_30px_rgba(124,58,237,0.45)]"
                : "text-zinc-400 hover:bg-white/5 hover:text-white"
            }`}
          >
            Log in
          </button>
          <button
            type="button"
            onClick={() => setModeSafe("register")}
            className={`rounded-xl px-3 py-2 text-sm font-medium transition ${
              mode === "register"
                ? "bg-gradient-to-r from-violet-600/90 to-blue-600/90 text-white shadow-[0_0_30px_rgba(124,58,237,0.45)]"
                : "text-zinc-400 hover:bg-white/5 hover:text-white"
            }`}
          >
            Sign up
          </button>
        </div>

        <div className="space-y-3">
          <Input type="email" label="Email" placeholder="email@example.com" value={email} onChange={setEmail} />

          {mode === "register" && (
            <Input type="text" label="Display name" placeholder="Tên hiển thị" value={displayName} onChange={setDisplayName} />
          )}

          {(mode === "login" || mode === "register") && (
            <PasswordInput
              label="Password"
              placeholder="Nhập mật khẩu"
              value={password}
              onChange={setPassword}
              visible={showPassword}
              onToggle={() => setShowPassword((v) => !v)}
            />
          )}

          {mode === "register" && (
            <PasswordInput
              label="Confirm password"
              placeholder="Nhập lại mật khẩu"
              value={confirmPassword}
              onChange={setConfirmPassword}
              visible={showConfirmPassword}
              onToggle={() => setShowConfirmPassword((v) => !v)}
            />
          )}

          {(mode === "verify" || mode === "reset") && (
            <Input type="text" label="Verification code" placeholder="Nhập mã xác minh" value={code} onChange={setCode} />
          )}

          {mode === "reset" && (
            <>
              <PasswordInput
                label="New password"
                placeholder="Mật khẩu mới"
                value={newPassword}
                onChange={setNewPassword}
                visible={showNewPassword}
                onToggle={() => setShowNewPassword((v) => !v)}
              />
              <PasswordInput
                label="Confirm new password"
                placeholder="Nhập lại mật khẩu mới"
                value={confirmNewPassword}
                onChange={setConfirmNewPassword}
                visible={showConfirmNewPassword}
                onToggle={() => setShowConfirmNewPassword((v) => !v)}
              />
            </>
          )}
        </div>

        {(error || message) && (
          <div className="mt-4 rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-zinc-100">
            {error || message}
          </div>
        )}

        {devCode && (
          <div className="mt-3 rounded-2xl border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-xs text-amber-100">
            Dev code: {devCode}
          </div>
        )}

        <div className="mt-5 space-y-2">
          {mode === "login" && (
            <PrimaryButton label={loading ? "Logging in..." : "Log in"} onClick={onLogin} disabled={loading} icon={<Shield size={16} />} />
          )}
          {mode === "register" && (
            <PrimaryButton label={loading ? "Creating..." : "Create account"} onClick={onRegister} disabled={loading} icon={<UserPlus size={16} />} />
          )}
          {mode === "verify" && (
            <>
              <PrimaryButton label={loading ? "Verifying..." : "Verify"} onClick={onVerify} disabled={loading} icon={<MailCheck size={16} />} />
              <SecondaryButton label="Resend code" onClick={onResendVerification} disabled={loading} />
            </>
          )}
          {mode === "forgot" && (
            <PrimaryButton
              label={loading ? "Sending..." : "Send reset code"}
              onClick={onRequestReset}
              disabled={loading}
              icon={<KeyRound size={16} />}
            />
          )}
          {mode === "reset" && (
            <PrimaryButton
              label={loading ? "Updating..." : "Update password"}
              onClick={onResetPassword}
              disabled={loading}
              icon={<KeyRound size={16} />}
            />
          )}
        </div>

        <div className="mt-5 flex flex-wrap gap-x-4 gap-y-2 text-xs text-zinc-400">
          {mode !== "login" && (
            <button type="button" onClick={() => setModeSafe("login")} className="text-violet-300 hover:text-violet-200">
              Back to login
            </button>
          )}
          {mode !== "register" && (
            <button type="button" onClick={() => setModeSafe("register")} className="text-violet-300 hover:text-violet-200">
              Create an account
            </button>
          )}
          {mode !== "forgot" && (
            <button type="button" onClick={() => setModeSafe("forgot")} className="text-violet-300 hover:text-violet-200">
              Forgot password?
            </button>
          )}
          {mode !== "verify" && (
            <button type="button" onClick={() => setModeSafe("verify")} className="text-violet-300 hover:text-violet-200">
              Verify email
            </button>
          )}
        </div>
      </AuthCard>
    </AuthShell>
  );
}

function Input({
  type,
  label,
  placeholder,
  value,
  onChange,
}: {
  type: string;
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-zinc-200">{label}</span>
      <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 transition focus-within:border-violet-400/70 focus-within:ring-2 focus-within:ring-violet-500/20">
        <input
          type={type}
          placeholder={placeholder}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full bg-transparent text-sm text-zinc-100 placeholder:text-zinc-500 outline-none"
        />
      </div>
    </label>
  );
}

function PasswordInput({
  label,
  placeholder,
  value,
  onChange,
  visible,
  onToggle,
}: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  visible: boolean;
  onToggle: () => void;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-zinc-200">{label}</span>
      <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 transition focus-within:border-violet-400/70 focus-within:ring-2 focus-within:ring-violet-500/20">
        <input
          type={visible ? "text" : "password"}
          placeholder={placeholder}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full bg-transparent text-sm text-zinc-100 placeholder:text-zinc-500 outline-none"
        />
        <button type="button" onClick={onToggle} className="text-zinc-400 hover:text-white" aria-label={visible ? "Ẩn mật khẩu" : "Hiện mật khẩu"}>
          {visible ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
    </label>
  );
}

function PrimaryButton({
  label,
  onClick,
  disabled,
  icon,
}: {
  label: string;
  onClick: () => void;
  disabled: boolean;
  icon: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-violet-600 via-fuchsia-600 to-blue-600 px-4 py-3 font-semibold text-white shadow-lg shadow-violet-900/30 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {icon}
      {label}
    </button>
  );
}

function SecondaryButton({
  label,
  onClick,
  disabled,
}: {
  label: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="w-full rounded-2xl border border-white/15 bg-white/[0.04] px-4 py-2.5 text-sm text-zinc-100 transition hover:border-white/30 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {label}
    </button>
  );
}


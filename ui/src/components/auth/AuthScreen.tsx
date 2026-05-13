"use client";

import React, { useMemo, useState } from "react";
import { Eye, EyeOff, KeyRound, MailCheck, Shield, UserPlus } from "lucide-react";
import { resendVerificationCode } from "@/services/auth";
import { useAuthStore } from "@/store/useAuthStore";
import AuthHero from "@/components/auth/AuthHero";

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

  const title = mode === "login" ? "Đăng nhập" : mode === "register" ? "Đăng ký" : mode === "verify" ? "Xác minh email" : mode === "forgot" ? "Quên mật khẩu" : "Đặt lại mật khẩu";
  const subtitle =
    mode === "login"
      ? "Tiếp tục cuộc trò chuyện an toàn của bạn."
      : mode === "register"
        ? "Tạo tài khoản để bắt đầu nhắn tin bảo mật."
        : mode === "verify"
          ? "Mã xác minh đã được gửi đến email của bạn."
          : mode === "forgot"
            ? "Nhập email để nhận mã đặt lại mật khẩu."
            : "Đặt mật khẩu mới để tiếp tục sử dụng tài khoản.";

  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950 text-slate-100">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_22%,rgba(34,211,238,0.16),transparent_30%),radial-gradient(circle_at_82%_4%,rgba(139,92,246,0.16),transparent_32%),radial-gradient(circle_at_75%_80%,rgba(59,130,246,0.12),transparent_30%)]" />
      <div className="relative mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-6 md:grid md:grid-cols-2 md:gap-8 md:px-8 md:py-10">
        <AuthHero />

        <section className="flex items-center justify-center">
          <div className="w-full max-w-lg rounded-3xl border border-white/10 bg-slate-900/80 p-5 shadow-2xl shadow-black/40 backdrop-blur-xl md:p-7">
            <div className="mb-5">
              <h2 className="text-2xl font-semibold text-white">{title}</h2>
              <p className="mt-1 text-sm text-slate-300">{subtitle}</p>
            </div>

            <div className="mb-5 grid grid-cols-2 rounded-xl border border-white/10 bg-slate-950/70 p-1">
              <button
                type="button"
                onClick={() => setModeSafe("login")}
                className={`rounded-lg px-3 py-2 text-sm font-medium transition ${mode === "login" ? "bg-indigo-500 text-white" : "text-slate-300 hover:text-white"}`}
              >
                Đăng nhập
              </button>
              <button
                type="button"
                onClick={() => setModeSafe("register")}
                className={`rounded-lg px-3 py-2 text-sm font-medium transition ${mode === "register" ? "bg-indigo-500 text-white" : "text-slate-300 hover:text-white"}`}
              >
                Đăng ký
              </button>
            </div>

            <div className="space-y-3">
              <Input
                type="email"
                placeholder="email@example.com"
                value={email}
                onChange={setEmail}
              />

              {mode === "register" && (
                <Input
                  type="text"
                  placeholder="Tên hiển thị"
                  value={displayName}
                  onChange={setDisplayName}
                />
              )}

              {(mode === "login" || mode === "register") && (
                <PasswordInput
                  placeholder="Mật khẩu"
                  value={password}
                  onChange={setPassword}
                  visible={showPassword}
                  onToggle={() => setShowPassword((v) => !v)}
                />
              )}

              {mode === "register" && (
                <PasswordInput
                  placeholder="Xác nhận mật khẩu"
                  value={confirmPassword}
                  onChange={setConfirmPassword}
                  visible={showConfirmPassword}
                  onToggle={() => setShowConfirmPassword((v) => !v)}
                />
              )}

              {(mode === "verify" || mode === "reset") && (
                <Input
                  type="text"
                  placeholder="Mã xác minh"
                  value={code}
                  onChange={setCode}
                />
              )}

              {mode === "reset" && (
                <>
                  <PasswordInput
                    placeholder="Mật khẩu mới"
                    value={newPassword}
                    onChange={setNewPassword}
                    visible={showNewPassword}
                    onToggle={() => setShowNewPassword((v) => !v)}
                  />
                  <PasswordInput
                    placeholder="Xác nhận mật khẩu mới"
                    value={confirmNewPassword}
                    onChange={setConfirmNewPassword}
                    visible={showConfirmNewPassword}
                    onToggle={() => setShowConfirmNewPassword((v) => !v)}
                  />
                </>
              )}
            </div>

            {(error || message) && (
              <div className="mt-4 rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-slate-200">{error || message}</div>
            )}

            {devCode && (
              <div className="mt-3 rounded-xl border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-xs text-amber-100">
                Dev code: {devCode}
              </div>
            )}

            <div className="mt-5 space-y-2">
              {mode === "login" && <PrimaryButton label={loading ? "Đang đăng nhập..." : "Đăng nhập"} onClick={onLogin} disabled={loading} icon={<Shield size={16} />} />}
              {mode === "register" && <PrimaryButton label={loading ? "Đang đăng ký..." : "Tạo tài khoản an toàn"} onClick={onRegister} disabled={loading} icon={<UserPlus size={16} />} />}
              {mode === "verify" && (
                <>
                  <PrimaryButton label={loading ? "Đang xác minh..." : "Xác minh email"} onClick={onVerify} disabled={loading} icon={<MailCheck size={16} />} />
                  <SecondaryButton label="Gửi lại mã" onClick={onResendVerification} disabled={loading} />
                </>
              )}
              {mode === "forgot" && <PrimaryButton label={loading ? "Đang gửi..." : "Gửi mã đặt lại"} onClick={onRequestReset} disabled={loading} icon={<KeyRound size={16} />} />}
              {mode === "reset" && <PrimaryButton label={loading ? "Đang đặt lại..." : "Đặt lại mật khẩu"} onClick={onResetPassword} disabled={loading} icon={<KeyRound size={16} />} />}
            </div>

            <div className="mt-5 flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-400">
              {mode !== "login" && <button type="button" onClick={() => setModeSafe("login")} className="hover:text-white">Về đăng nhập</button>}
              {mode !== "register" && <button type="button" onClick={() => setModeSafe("register")} className="hover:text-white">Tạo tài khoản</button>}
              {mode !== "forgot" && <button type="button" onClick={() => setModeSafe("forgot")} className="hover:text-white">Quên mật khẩu?</button>}
              {mode !== "verify" && <button type="button" onClick={() => setModeSafe("verify")} className="hover:text-white">Xác minh email</button>}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function Input({
  type,
  placeholder,
  value,
  onChange,
}: {
  type: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <input
      type={type}
      placeholder={placeholder}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="h-11 w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-400/25"
    />
  );
}

function PasswordInput({
  placeholder,
  value,
  onChange,
  visible,
  onToggle,
}: {
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  visible: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="relative">
      <input
        type={visible ? "text" : "password"}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 pr-10 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-400/25"
      />
      <button
        type="button"
        onClick={onToggle}
        className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-400 hover:text-white"
        aria-label={visible ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
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
      className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 via-violet-500 to-blue-500 text-sm font-medium text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
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
      className="h-10 w-full rounded-xl border border-white/15 bg-slate-950/60 text-sm text-slate-100 transition hover:border-white/30 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {label}
    </button>
  );
}


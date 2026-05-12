"use client";
import React, { useEffect, useMemo, useState } from "react";
import { changePassword, deleteAccount, getMe, updateProfile } from "@/services/auth";
import { useAuthStore } from "@/store/useAuthStore";
import { useChatStore } from "@/store/useChatStore";
import { useSignatureStore } from "@/store/useSignatureStore";

export default function ProfileSettings() {
  const currentUser = useAuthStore((s) => s.currentUser);
  const logout = useAuthStore((s) => s.logout);
  const setCurrentUser = useAuthStore((s) => s.setCurrentUser);
  const resetChat = useChatStore((s) => s.reset);
  const clearSigned = useSignatureStore((s) => s.clearSignedFiles);

  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [deletePassword, setDeletePassword] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState("");

  const email = useMemo(() => (currentUser?.email || currentUser?.id || "").trim().toLowerCase(), [currentUser]);
  const userId = useMemo(() => (currentUser?.id || currentUser?.email || "").trim().toLowerCase(), [currentUser]);

  useEffect(() => {
    if (!email) return;
    void getMe(email)
      .then((res) => {
        setDisplayName(res.user.display_name || "");
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Không tải được hồ sơ.");
      });
  }, [email]);

  const saveProfile = async () => {
    if (!email) return;
    setLoading(true);
    setMessage("");
    setError("");
    try {
      const res = await updateProfile({ email, display_name: displayName.trim() });
      setCurrentUser({
        id: userId,
        email,
        displayName: displayName.trim(),
      });
      setMessage(res.message || "Cập nhật hồ sơ thành công.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể cập nhật hồ sơ.");
    } finally {
      setLoading(false);
    }
  };

  const doChangePassword = async () => {
    if (!email) return;
    if (newPassword !== confirmPassword) {
      setError("Mật khẩu mới và xác nhận không khớp.");
      return;
    }
    setLoading(true);
    setMessage("");
    setError("");
    try {
      const res = await changePassword({ email, current_password: currentPassword, new_password: newPassword });
      setMessage(res.message || "Đổi mật khẩu thành công.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể đổi mật khẩu.");
    } finally {
      setLoading(false);
    }
  };

  const doDeleteAccount = async () => {
    if (!email) return;
    if (deleteConfirm !== "DELETE" && deleteConfirm !== email) {
      setError("Nhập DELETE hoặc email để xác nhận xóa tài khoản.");
      return;
    }
    setLoading(true);
    setMessage("");
    setError("");
    try {
      const res = await deleteAccount({ email, password: deletePassword });
      setMessage(res.message || "Đã xóa tài khoản.");
      clearSigned();
      resetChat();
      logout();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể xóa tài khoản.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-3 space-y-4">
      <h4 className="font-semibold mb-2">Hồ sơ người dùng</h4>

      <div className="space-y-2 rounded border border-slate-800 p-3">
        <label className="text-sm">User ID (không thể sửa)</label>
        <input value={userId} readOnly className="bg-slate-800 rounded-md px-2 py-1 w-full opacity-80" />
        <label className="text-sm">Email (không thể sửa)</label>
        <input value={email} readOnly className="bg-slate-800 rounded-md px-2 py-1 w-full opacity-80" />
        <label className="text-sm">Tên hiển thị</label>
        <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} className="bg-slate-800 rounded-md px-2 py-1 w-full" />
        <div className="flex justify-end">
          <button disabled={loading || !email} onClick={saveProfile} className="px-3 py-2 bg-indigo-600 rounded-md disabled:opacity-50">Lưu hồ sơ</button>
        </div>
      </div>

      <div className="space-y-2 rounded border border-slate-800 p-3">
        <h5 className="font-medium">Đổi mật khẩu</h5>
        <input type="password" placeholder="Mật khẩu hiện tại" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} className="bg-slate-800 rounded-md px-2 py-1 w-full" />
        <input type="password" placeholder="Mật khẩu mới" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="bg-slate-800 rounded-md px-2 py-1 w-full" />
        <input type="password" placeholder="Xác nhận mật khẩu mới" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="bg-slate-800 rounded-md px-2 py-1 w-full" />
        <div className="flex justify-end">
          <button disabled={loading || !email} onClick={doChangePassword} className="px-3 py-2 bg-indigo-600 rounded-md disabled:opacity-50">Đổi mật khẩu</button>
        </div>
      </div>

      <div className="space-y-2 rounded border border-red-900/60 p-3">
        <h5 className="font-medium text-red-300">Xóa tài khoản</h5>
        <p className="text-xs text-slate-300">Hành động này sẽ xóa tài khoản, hồ sơ, thông báo và dữ liệu hội thoại liên quan.</p>
        <input type="password" placeholder="Mật khẩu" value={deletePassword} onChange={(e) => setDeletePassword(e.target.value)} className="bg-slate-800 rounded-md px-2 py-1 w-full" />
        <input placeholder='Nhập "DELETE" hoặc email để xác nhận' value={deleteConfirm} onChange={(e) => setDeleteConfirm(e.target.value)} className="bg-slate-800 rounded-md px-2 py-1 w-full" />
        <div className="flex justify-end">
          <button disabled={loading || !email} onClick={doDeleteAccount} className="px-3 py-2 bg-red-700 rounded-md disabled:opacity-50">Xóa tài khoản</button>
        </div>
      </div>

      {message && <div className="text-xs text-emerald-300">{message}</div>}
      {error && <div className="text-xs text-red-300">{error}</div>}
    </div>
  );
}

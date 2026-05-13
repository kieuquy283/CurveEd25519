"use client";

import React, { useMemo, useState } from "react";
import { CheckCircle2, AlertTriangle, Clock3, RefreshCcw } from "lucide-react";
import GlobalModal from "@/components/ui/GlobalModal";
import { ConnectionStatusResponse, requestConnection, verifyConnection } from "@/services/connections";

interface Props {
  open: boolean;
  onClose: () => void;
  status: ConnectionStatusResponse | null;
  currentUser: string;
  peerIdentifier: string;
  onStatusRefresh?: (status: ConnectionStatusResponse) => void;
  onVerified?: (status: ConnectionStatusResponse) => void;
  refreshStatus: (user: string, peer: string) => Promise<ConnectionStatusResponse>;
}

function StatusItem({ ok, label, pending }: { ok: boolean; label: string; pending?: boolean }) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm">
      {ok ? (
        <CheckCircle2 size={15} className="text-emerald-400" />
      ) : pending ? (
        <Clock3 size={15} className="text-amber-400" />
      ) : (
        <AlertTriangle size={15} className="text-red-400" />
      )}
      <span>{label}</span>
    </div>
  );
}

export default function VerifyConnectionRequiredModal({
  open,
  onClose,
  status,
  currentUser,
  peerIdentifier,
  onStatusRefresh,
  onVerified,
  refreshStatus,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState("");

  const isRecipient = useMemo(() => {
    if (!status?.connection?.exists) return false;
    return String(status.connection.recipient_email || "").toLowerCase() === currentUser.toLowerCase();
  }, [currentUser, status?.connection]);

  if (!open) return null;

  const reason = status?.reason || "missing_connection";

  return (
    <GlobalModal open={open} onClose={onClose} size="lg" title="Xác minh kết nối trước khi gửi">
      <div className="w-full">
        <div className="border-b border-white/10 px-6 py-5">
          <h3 className="text-lg font-semibold">Xác minh kết nối trước khi gửi</h3>
          <p className="mt-1 text-sm text-zinc-300">
            Để gửi tin nhắn mã hóa đầu cuối, bạn cần xác minh người nhận và trao đổi khóa công khai X25519/Ed25519.
          </p>
        </div>

        <div className="space-y-4 p-6">
          <StatusItem ok={Boolean(status?.peer?.account_exists)} label="Tài khoản người nhận tồn tại" />
          <StatusItem ok={Boolean(status?.peer?.verified)} label="Email người nhận đã xác minh" />
          <StatusItem
            ok={Boolean(status?.peer?.profile_exists && status?.peer?.has_x25519_public_key && status?.peer?.has_ed25519_public_key)}
            label="Hồ sơ khóa công khai đã sẵn sàng"
          />
          <StatusItem ok={Boolean(status?.connection?.status === "verified")} pending={status?.connection?.status === "pending"} label="Kết nối đã xác minh" />

          {reason === "peer_not_found" && <div className="text-sm text-red-300">Không tìm thấy tài khoản người nhận.</div>}
          {reason === "peer_not_verified" && <div className="text-sm text-amber-300">Người nhận chưa xác minh email.</div>}
          {reason === "missing_crypto_profile" && <div className="text-sm text-amber-300">Người nhận chưa có hồ sơ khóa công khai.</div>}
          {reason === "pending_connection" && !isRecipient && <div className="text-sm text-amber-300">Đang chờ người nhận xác minh kết nối.</div>}

          {msg && <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-zinc-200">{msg}</div>}

          <div className="flex flex-wrap gap-2">
            {reason === "missing_connection" && (
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setMsg("");
                  try {
                    const res = await requestConnection({ from_user: currentUser, to: peerIdentifier });
                    const updated = await refreshStatus(currentUser, peerIdentifier);
                    onStatusRefresh?.(updated);
                    setMsg(res?.message || "Đã gửi yêu cầu kết nối.");
                  } catch (error) {
                    setMsg(error instanceof Error ? error.message : "Không thể gửi yêu cầu kết nối.");
                  } finally {
                    setBusy(false);
                  }
                }}
                className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm hover:bg-white/[0.08]"
              >
                Gửi yêu cầu kết nối
              </button>
            )}

            {reason === "pending_connection" && isRecipient && (
              <>
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="Mã xác minh email"
                  className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm"
                />
                <button
                  type="button"
                  disabled={busy || !code.trim() || !status?.connection?.id}
                  onClick={async () => {
                    if (!status?.connection?.id) return;
                    setBusy(true);
                    setMsg("");
                    try {
                      await verifyConnection({ connection_id: status.connection.id, user: currentUser, code: code.trim() });
                      const updated = await refreshStatus(currentUser, peerIdentifier);
                      onStatusRefresh?.(updated);
                      if (updated.can_send_encrypted) onVerified?.(updated);
                      setMsg(updated.can_send_encrypted ? "Kết nối đã xác minh." : "Đã gửi xác minh, vui lòng kiểm tra lại.");
                    } catch (error) {
                      setMsg(error instanceof Error ? error.message : "Xác minh thất bại.");
                    } finally {
                      setBusy(false);
                    }
                  }}
                  className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm hover:bg-white/[0.08]"
                >
                  Xác minh kết nối
                </button>
              </>
            )}

            <button
              type="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setMsg("");
                try {
                  const updated = await refreshStatus(currentUser, peerIdentifier);
                  onStatusRefresh?.(updated);
                  if (updated.can_send_encrypted) {
                    setMsg("Đã kết nối an toàn. Bạn có thể gửi tin nhắn mã hóa.");
                    onVerified?.(updated);
                  }
                } catch (error) {
                  setMsg(error instanceof Error ? error.message : "Không thể kiểm tra lại kết nối.");
                } finally {
                  setBusy(false);
                }
              }}
              className="inline-flex items-center gap-1 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm hover:bg-white/[0.08]"
            >
              <RefreshCcw size={14} />
              Kiểm tra lại
            </button>

            <button type="button" onClick={onClose} className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm hover:bg-white/[0.08]">
              Đóng
            </button>
          </div>
        </div>
      </div>
    </GlobalModal>
  );
}

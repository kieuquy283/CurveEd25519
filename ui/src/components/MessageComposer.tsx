"use client";

import React, { ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, FileCheck2, FileSignature, FileUp, Loader2, Send, ShieldAlert, X } from "lucide-react";

import { useChatStore } from "@/store/useChatStore";
import { getCurrentUserId, useAuthStore } from "@/store/useAuthStore";
import { websocketService } from "@/services/websocket";
import { saveConversationMessage } from "@/services/conversations";
import {
  encryptConversationMessage,
  signFileContainer,
  verifySignedFileContainer,
  getConversationApiBaseUrl,
} from "@/services/conversationCrypto";
import { buildApiBaseCandidates } from "@/config/env";
import { ChatMessage, SignedFileContainer, VerificationResult } from "@/types/models";
import { ConnectionStatusResponse } from "@/services/connections";
import VerificationResultOverlay from "@/components/ui/VerificationResultOverlay";
import { useVerificationOverlay } from "@/hooks/useVerificationOverlay";
import { normalizeChatAttachment } from "@/lib/normalizeAttachment";

import { buildPacketId, buildTimestamp, PacketType } from "@/types/packets";
import { normalizeEmail } from "@/services/connections";

interface Props {
  conversationId: string;
  peerIdentifier: string;
  connectionStatus?: ConnectionStatusResponse | null;
  onConnectionStatusChange?: (status: ConnectionStatusResponse) => void;
  onOpenConnectionStatusModal?: () => void;
  refreshConnectionStatus: (userEmail: string, peerIdentifier: string) => Promise<ConnectionStatusResponse>;
}

interface PendingFile {
  id: string;
  file: File;
  dataBase64: string;
}
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result);
      resolve(result.split(",")[1] ?? result);
    };
    reader.onerror = () => {
      reject(reader.error ?? new Error("Failed to read file"));
    };
    reader.readAsDataURL(file);
  });
}

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function downloadTextFile(filename: string, content: string, mimeType = "application/json") {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function downloadBase64File(filename: string, mimeType: string, contentB64: string) {
  const url = `data:${mimeType};base64,${contentB64}`;
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
}

function decodeSignedContainerFromBase64(base64: string): SignedFileContainer | null {
  try {
    const binary = atob(base64);
    const bytes = Uint8Array.from(binary, (ch) => ch.charCodeAt(0));
    const text = new TextDecoder().decode(bytes);
    const parsed = JSON.parse(text) as SignedFileContainer;
    if (parsed && parsed.type === "signed-file" && parsed.filename && parsed.content_b64) {
      return parsed;
    }
  } catch {
    return null;
  }
  return null;
}

const CONNECTION_STATUS_CACHE_MS = 60_000;
const connectionStatusCheckedAt = new Map<string, number>();

export function MessageComposer({
  conversationId,
  peerIdentifier,
  connectionStatus,
  onConnectionStatusChange,
  onOpenConnectionStatusModal,
  refreshConnectionStatus,
}: Props) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [pendingFile, setPendingFile] = useState<PendingFile | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<VerificationResult | null>(null);
  const [verifiedContainer, setVerifiedContainer] = useState<SignedFileContainer | null>(null);
  const [backendReachable, setBackendReachable] = useState<boolean | null>(null);
  const { overlay, showVerified, showFailed } = useVerificationOverlay();

  const inputRef = useRef<HTMLInputElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const signFileInputRef = useRef<HTMLInputElement | null>(null);
  const verifyFileInputRef = useRef<HTMLInputElement | null>(null);

  const chatStore = useChatStore.getState();
  const currentUserEmail = useAuthStore((s) => s.currentUser?.email);

  useEffect(() => {
    let stopped = false;

    const checkBackend = async () => {
      try {
        const primary = getConversationApiBaseUrl().replace(/\/+$/, "");
        const uniqueCandidates = buildApiBaseCandidates(primary);
        let ok = false;

        for (const base of uniqueCandidates) {
          try {
            const response = await fetch(`${base}/`, {
              method: "GET",
            });
            if (response.ok) {
              ok = true;
              break;
            }
          } catch {
            continue;
          }
        }

        if (!stopped) {
          setBackendReachable(ok);
        }
      } catch {
        if (!stopped) {
          setBackendReachable(false);
        }
      }
    };

    checkBackend();
    const interval = setInterval(checkBackend, 10000);

    return () => {
      stopped = true;
      clearInterval(interval);
    };
  }, []);

  const encryptMessage = useCallback(
    async (plaintext: string) =>
      encryptConversationMessage({
        sender: getCurrentUserId(),
        recipient: peerIdentifier,
        plaintext,
      }),
    [peerIdentifier]
  );

  const handlePickFile = useCallback(() => {
    if (!sending) fileInputRef.current?.click();
  }, [sending]);

  const handleFileChange = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > MAX_FILE_SIZE_BYTES) {
      alert("File quá lớn. Giới hạn 10MB.");
      return;
    }
    try {
      const dataBase64 = await fileToBase64(file);
      setPendingFile({ id: crypto.randomUUID(), file, dataBase64 });
    } catch (error) {
      console.error("Read file failed:", error);
    }
  }, []);

  const handleSignFile = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      const content_b64 = await fileToBase64(file);
      const result = await signFileContainer({
        signer: getCurrentUserId(),
        filename: file.name,
        mime_type: file.type || "application/octet-stream",
        content_b64,
      });
      if (!result?.ok || !result.signed_file) {
        throw new Error("Invalid sign-file response");
      }

      const signedName = `${file.name}.signed.json`;
      const signedText = JSON.stringify(result.signed_file, null, 2);
      downloadTextFile(signedName, signedText);

      const signedBlobFile = new File([signedText], signedName, {
        type: "application/json",
      });
      const signedB64 = await fileToBase64(signedBlobFile);
      setPendingFile({
        id: crypto.randomUUID(),
        file: signedBlobFile,
        dataBase64: signedB64,
      });
    } catch (error) {
      console.error("[Composer] Sign file failed:", error);
    }
  }, []);

  const handleVerifySignedFile = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setVerifying(true);
    setVerifyResult(null);
    setVerifiedContainer(null);
    try {
      const textContent = await file.text();
      const container = JSON.parse(textContent) as SignedFileContainer;
      const result = await verifySignedFileContainer({
        signed_file: container,
        verifier: getCurrentUserId(),
      });
      setVerifyResult(result);
      setVerifiedContainer(container);
      if (result.valid) {
        showVerified();
      } else {
        showFailed(result.message || "Chữ ký không hợp lệ");
      }
    } catch (error) {
      console.error("[Composer] Verify signed file failed:", error);
      setVerifyResult({
        ok: true,
        valid: false,
        message: "File đã bị thay đổi hoặc chữ ký không hợp lệ.",
        debug: {
          algorithm: "Ed25519",
          hash: "SHA-256",
          signer: "unknown",
        },
      });
      showFailed("Không thể xác minh chữ ký");
    } finally {
      setVerifying(false);
    }
  }, [showFailed, showVerified]);

  const clearFile = useCallback(() => {
    if (!sending) setPendingFile(null);
  }, [sending]);

  const handleSend = useCallback(async () => {
    const currentUserId = normalizeEmail(currentUserEmail || getCurrentUserId());
    const file = pendingFile;
    const trimmed = text.trim();
    if ((!trimmed && !file) || sending) return;
    const peerEmail = normalizeEmail(peerIdentifier);
    const cacheKey = [currentUserId, peerEmail].sort().join("::");
    const lastChecked = connectionStatusCheckedAt.get(cacheKey) ?? 0;
    const nowMs = Date.now();
    const cachedValid =
      Boolean(connectionStatus?.can_send_encrypted) &&
      nowMs - lastChecked < CONNECTION_STATUS_CACHE_MS;
    const latestStatus = cachedValid
      ? connectionStatus
      : await refreshConnectionStatus(currentUserId, peerEmail).catch(() => connectionStatus ?? null);
    if (latestStatus?.can_send_encrypted) {
      connectionStatusCheckedAt.set(cacheKey, nowMs);
    }
    if (!latestStatus || !latestStatus.can_send_encrypted) {
      if (latestStatus) onConnectionStatusChange?.(latestStatus);
      onOpenConnectionStatusModal?.();
      return;
    }

    setSending(true);
    const messageId = `tmp-${crypto.randomUUID()}`;
    const clientMessageId = crypto.randomUUID();
    const now = new Date().toISOString();
    const isFileMessage = Boolean(file);

    const signedContainer =
      file && file.file.name.toLowerCase().endsWith(".signed.json")
        ? decodeSignedContainerFromBase64(file.dataBase64)
        : null;

    const attachmentPayload = file
      ? {
          id: file.id,
          type: signedContainer ? "signed-file" : "file",
          kind: signedContainer ? "signed-file" : "file",
          fileName: file.file.name,
          mimeType: file.file.type || "application/octet-stream",
          size: file.file.size,
          dataBase64: file.dataBase64,
          content_b64: file.dataBase64,
          signed_file_json: signedContainer ?? undefined,
          signed_file: signedContainer ?? undefined,
          signature: signedContainer
            ? {
                signer: signedContainer.signer,
                signed_at: signedContainer.signed_at,
                algorithm: signedContainer.algorithm,
                hash: signedContainer.hash,
              }
            : undefined,
          original_file: signedContainer
            ? {
                filename: signedContainer.filename,
                mime_type: signedContainer.mimeType,
                size: signedContainer.size,
                content_b64: signedContainer.content_b64,
              }
            : undefined,
          crypto: {
            encrypted: true,
            decrypted: true,
            encryption: "ChaCha20-Poly1305",
            keyExchange: "X25519",
            kdf: "HKDF-SHA256",
            signature: "Ed25519",
          },
        }
      : null;

    const plaintext = isFileMessage
      ? JSON.stringify({
          type: "file",
          text: trimmed,
          attachment: attachmentPayload,
        })
      : trimmed;

    const outgoingMessage: ChatMessage = {
      id: messageId,
      clientMessageId,
      conversationId,
      from: currentUserId,
      to: conversationId,
      text: isFileMessage ? trimmed || `📎 ${file?.file.name ?? "Attachment"}` : trimmed,
      timestamp: now,
      status: "pending",
      type: isFileMessage ? "file" : "text",
      cryptoDirection: "encrypt",
      attachments:
        file && attachmentPayload
          ? [
              normalizeChatAttachment({
                ...attachmentPayload,
                url: `data:${attachmentPayload.mimeType};base64,${attachmentPayload.dataBase64}`,
              })!,
            ]
          : [],
    };
    chatStore.addMessage(outgoingMessage);

    setText("");
    setPendingFile(null);

    try {
      const encrypted = await encryptMessage(plaintext);
      if (!encrypted?.ok || !encrypted?.envelope) throw new Error("Invalid encrypt response");

      chatStore.updateMessageCrypto(messageId, conversationId, {
        envelope: encrypted.envelope,
        cryptoDebug: {
          ...(encrypted.debug ?? {}),
          contentType: isFileMessage ? "file" : "text",
        },
        cryptoDirection: "encrypt",
        status: "queued",
      });

      const packetId = buildPacketId();
      const packet = {
        packet_id: packetId,
        packet_type: PacketType.MESSAGE,
        sender_id: currentUserId,
        receiver_id: peerEmail,
        created_at: buildTimestamp(),
        requires_ack: true,
        encrypted: true,
        payload: {
          envelope: encrypted.envelope,
          conversation_id: conversationId,
          client_message_id: clientMessageId,
          plaintext_preview: trimmed.slice(0, 200),
          message_type: isFileMessage ? "file" : "text",
        },
      };

      try {
        await websocketService.sendPacket(packet);
      } catch (wsError) {
        console.warn(
          "[Composer] WebSocket not connected. Message encrypted and stored locally:",
          wsError
        );
      }

      try {
        const saved = await saveConversationMessage(conversationId, {
          sender_email: currentUserId,
          receiver_email: peerEmail,
          packet_id: packet.packet_id,
          message_type: isFileMessage ? "file" : "text",
          ciphertext_envelope: encrypted.envelope as Record<string, unknown>,
          plaintext_preview: trimmed.slice(0, 200),
          attachment_json: attachmentPayload as Record<string, unknown> | undefined,
          crypto_debug: (encrypted.debug ?? {}) as Record<string, unknown>,
          status: "sent",
        });
        const savedMessage = saved.message || {};
        chatStore.replaceMessage(conversationId, messageId, {
          ...outgoingMessage,
          id: String(savedMessage.id || packetId),
          packetId: String(savedMessage.packet_id || packetId),
          clientMessageId,
          timestamp: String(savedMessage.created_at || now),
          status: "sent",
          envelope: (savedMessage.ciphertext_envelope as Record<string, unknown> | undefined) || encrypted.envelope,
        });
      } catch (persistError) {
        console.warn("[Composer] saveConversationMessage failed:", persistError);
        chatStore.updateMessageStatus(messageId, conversationId, "sent");
      }
    } catch (error) {
      console.error("[Composer] Backend crypto API unreachable or encrypt failed:", error);
      const detail = error instanceof Error ? error.message : "Không kết nối được backend crypto API. Vui lòng thử lại.";
      if (detail.includes("verified_connection_required")) {
        const refreshed = await refreshConnectionStatus(currentUserId, peerIdentifier).catch(() => null);
        if (refreshed) onConnectionStatusChange?.(refreshed);
        onOpenConnectionStatusModal?.();
      } else {
        alert(detail || "Không kết nối được backend crypto API. Vui lòng thử lại.");
      }
      chatStore.updateMessageStatus(messageId, conversationId, "failed");
    } finally {
      setSending(false);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [
    conversationId,
    peerIdentifier,
    currentUserEmail,
    encryptMessage,
    pendingFile,
    sending,
    text,
    chatStore,
    connectionStatus,
    onConnectionStatusChange,
    onOpenConnectionStatusModal,
    refreshConnectionStatus,
  ]);

  return (
    <div className="border-t border-white/10 bg-slate-950/70 p-4 backdrop-blur-xl">
      <VerificationResultOverlay
        open={overlay.open}
        status={overlay.status}
        title={overlay.title}
        message={overlay.message}
      />
      {pendingFile && (
        <div className="mb-3 flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-medium text-zinc-100">{pendingFile.file.name}</div>
            <div className="mt-1 text-xs text-zinc-400">
              {formatFileSize(pendingFile.file.size)} · {pendingFile.file.type || "application/octet-stream"}
            </div>
            <div className="mt-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
              <div>Mã hóa: ChaCha20-Poly1305</div>
              <div>Trao đổi khóa: X25519</div>
              <div>KDF: HKDF-SHA256</div>
              <div>Chữ ký: Ed25519</div>
              <div>Giải mã: Thành công sau khi người nhận mở envelope</div>
            </div>
          </div>
          <button
            type="button"
            disabled={sending}
            onClick={clearFile}
            className="ml-3 rounded-lg p-2 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-50"
          >
            <X size={16} />
          </button>
        </div>
      )}

        <div className="mb-3 flex flex-wrap gap-2">
        <div
          className={`inline-flex items-center rounded-lg border px-3 py-2 text-xs ${
            backendReachable === true
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
              : backendReachable === false
                ? "border-red-500/40 bg-red-500/10 text-red-200"
                : "border-white/10 bg-white/[0.04] text-zinc-300"
          }`}
        >
          {backendReachable === true
            ? "Backend crypto API: Online"
            : backendReachable === false
              ? "Backend crypto API: Offline"
              : "Backend crypto API: Checking..."}
        </div>

        <input ref={signFileInputRef} type="file" className="hidden" onChange={handleSignFile} />
        <button
          type="button"
          onClick={() => signFileInputRef.current?.click()}
          className="inline-flex items-center gap-1 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-zinc-200 hover:bg-violet-500/10"
        >
          <FileSignature size={14} />
          Ký file
        </button>

        <input
          ref={verifyFileInputRef}
          type="file"
          accept=".json,.signed.json,application/json"
          className="hidden"
          onChange={handleVerifySignedFile}
        />
        <button
          type="button"
          disabled={verifying}
          onClick={() => verifyFileInputRef.current?.click()}
          className="inline-flex items-center gap-1 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-zinc-200 hover:bg-violet-500/10 disabled:opacity-50"
        >
          <FileCheck2 size={14} />
          Xác minh chữ ký
        </button>
      </div>

      {verifyResult && (
        <div className="mb-3 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-xs">
          <div className="mb-1 flex items-center justify-between">
            <div className="text-zinc-100 font-medium">
              Kết quả xác minh chữ ký
            </div>
            <button
              type="button"
              onClick={() => {
                setVerifyResult(null);
                setVerifiedContainer(null);
              }}
              className="inline-flex items-center gap-1 rounded-md border border-zinc-700 px-2 py-1 text-[11px] text-zinc-300 hover:border-zinc-500 hover:text-zinc-100"
              title="Ẩn kết quả"
            >
              <X size={12} />
              Ẩn kết quả
            </button>
          </div>
          {verifiedContainer && (
            <>
              <div className="text-zinc-300">File: {verifiedContainer.filename}</div>
              <div className="text-zinc-300">Signer: {verifiedContainer.signer}</div>
              <div className="text-zinc-300">Signed at: {verifiedContainer.signed_at}</div>
              <div className="text-zinc-300">Algorithm: {verifiedContainer.algorithm}</div>
              <div className="text-zinc-300">Hash: {verifiedContainer.hash}</div>
            </>
          )}
          <div className={`mt-2 inline-flex items-center gap-1 ${verifyResult.valid ? "text-emerald-300" : "text-red-300"}`}>
            {verifyResult.valid ? <CheckCircle2 size={14} /> : <ShieldAlert size={14} />}
            {verifyResult.valid ? "Chữ ký hợp lệ" : "File đã bị thay đổi hoặc chữ ký không hợp lệ."}
          </div>
          {verifyResult.valid && verifyResult.file && (
            <div className="mt-2">
              <button
                type="button"
                onClick={() =>
                  downloadBase64File(
                    verifyResult.file!.filename,
                    verifyResult.file!.mime_type,
                    verifyResult.file!.content_b64
                  )
                }
                className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-emerald-200"
              >
                Tải file gốc
              </button>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-2 rounded-[1.75rem] border border-white/10 bg-white/[0.05] px-3 py-2 shadow-[0_0_35px_rgba(15,23,42,0.4)] focus-within:border-violet-400/60 focus-within:ring-2 focus-within:ring-violet-500/20">
        <input ref={fileInputRef} type="file" className="hidden" onChange={handleFileChange} />

        <button
          type="button"
          disabled={sending}
          onClick={handlePickFile}
          className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-zinc-300 transition-colors hover:bg-violet-500/15 hover:text-white disabled:opacity-50"
          title="Upload encrypted file"
        >
          <FileUp size={18} />
        </button>

        <input
          ref={inputRef}
          value={text}
          disabled={sending}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              handleSend();
            }
          }}
          placeholder={pendingFile ? "Thêm chú thích..." : "Nhập tin nhắn mã hóa..."}
          aria-label="Nhập tin nhắn"
          className="flex-1 bg-transparent px-2 py-3 text-sm text-zinc-100 outline-none placeholder:text-zinc-500 disabled:opacity-60"
        />

        <button
          type="button"
          disabled={sending || (!text.trim() && !pendingFile)}
          onClick={handleSend}
          aria-label="Gửi tin nhắn"
          className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-600 to-blue-600 transition hover:brightness-110 disabled:opacity-50"
        >
          {sending ? <Loader2 size={18} className="animate-spin text-white" /> : <Send size={18} className="text-white" />}
        </button>
      </div>
    </div>
  );
}

export default MessageComposer;


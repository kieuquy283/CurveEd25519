"use client";

import React, { ChangeEvent, useMemo, useRef, useState } from "react";
import { Download, Loader2, X } from "lucide-react";

import { signFile } from "@/services/signature";
import { useSignatureStore } from "@/store/useSignatureStore";
import { useAuthStore } from "@/store/useAuthStore";
import { SignedFileContainer } from "@/types/models";

interface SignatureDialogProps {
  open: boolean;
  onClose: () => void;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result);
      resolve(result.split(",")[1] ?? result);
    };
    reader.onerror = () =>
      reject(reader.error ?? new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function confirmSignedDownload() {
  return window.confirm(
    "Download signed file?\n\nThis will download the signed JSON container. Recipients can verify the file integrity with Ed25519."
  );
}

function downloadSignedContainer(container: SignedFileContainer) {
  if (!confirmSignedDownload()) {
    return;
  }

  const filename = `${container.filename}.signed.json`;
  const blob = new Blob([JSON.stringify(container, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function SignatureDialog({
  open,
  onClose,
}: SignatureDialogProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSigning, setIsSigning] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [latestSignedContainer, setLatestSignedContainer] =
    useState<SignedFileContainer | null>(null);

  const signedFiles = useSignatureStore((s) => s.signedFiles);
  const addSignedFile = useSignatureStore((s) => s.addSignedFile);
  const currentUser = useAuthStore((s) => s.currentUser);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const fileInfo = useMemo(() => {
    if (!selectedFile) return null;
    return {
      name: selectedFile.name,
      mimeType: selectedFile.type || "application/octet-stream",
      size: selectedFile.size,
    };
  }, [selectedFile]);

  if (!open) return null;

  const handleSelectFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    event.target.value = "";
    setSelectedFile(file);
    setError("");
    setSuccess("");
  };

  const handleSignFile = async () => {
    if (!selectedFile || isSigning) return;
    const signer = (currentUser?.email || currentUser?.id || "").trim().toLowerCase();
    if (!signer) {
      setError("Vui lòng đăng nhập trước khi ký file.");
      return;
    }
    try {
      setIsSigning(true);
      setError("");
      setSuccess("");
      const content_b64 = await fileToBase64(selectedFile);
      const result = await signFile({
        signer,
        filename: selectedFile.name,
        mime_type: selectedFile.type || "application/octet-stream",
        content_b64,
      });

      if (!result.ok || !result.signed_file) {
        throw new Error("Invalid sign-file response");
      }

      addSignedFile({
        id: crypto.randomUUID(),
        filename: result.signed_file.filename,
        size: result.signed_file.size,
        signer: result.signed_file.signer,
        signed_at: result.signed_file.signed_at,
        algorithm: "Ed25519",
        hash: "SHA-256",
        container: result.signed_file,
      });

      setLatestSignedContainer(result.signed_file);
      setSuccess("Ký file thành công.");
    } catch (signError) {
      console.error("[SignatureDialog] Sign failed:", signError);
      const message =
        signError instanceof Error ? signError.message : "Unknown error";
      const detail = message.includes(":")
        ? message.split(":").slice(1).join(":").trim()
        : message;
      setError(detail || "Không thể ký file. Vui lòng kiểm tra backend hoặc profile ký.");
    } finally {
      setIsSigning(false);
    }
  };

  const handleClearSelectedFile = () => {
    setSelectedFile(null);
    setError("");
    setSuccess("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-black/70"
        onClick={onClose}
        aria-label="Close signature dialog"
      />

      <div className="relative z-10 w-full max-w-3xl rounded-2xl border border-zinc-800 bg-zinc-900 text-zinc-100 shadow-2xl">
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <div>
            <h3 className="text-lg font-semibold">Chữ ký số / Ký file</h3>
            <p className="text-xs text-zinc-400">
              Ký file bằng Ed25519 để người nhận có thể xác minh toàn vẹn và phát hiện thay đổi.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
          >
            <X size={18} />
          </button>
        </div>

        <div className="space-y-4 p-5">
          <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <label className="inline-flex cursor-pointer items-center rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm hover:border-blue-500">
                Chọn file
                <input ref={fileInputRef} type="file" className="hidden" onChange={handleSelectFile} />
              </label>
              <button
                type="button"
                disabled={!selectedFile || isSigning}
                onClick={handleSignFile}
                className="inline-flex items-center gap-1 rounded-lg border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-sm text-blue-200 disabled:opacity-50"
              >
                {isSigning ? <Loader2 size={14} className="animate-spin" /> : null}
                Ký file
              </button>
              <button
                type="button"
                disabled={!selectedFile || isSigning}
                onClick={handleClearSelectedFile}
                className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 hover:border-zinc-500 disabled:opacity-50"
              >
                Hủy chọn file
              </button>
              <button
                type="button"
                disabled={!latestSignedContainer}
                onClick={() => latestSignedContainer && downloadSignedContainer(latestSignedContainer)}
                className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 hover:border-blue-500 disabled:opacity-50"
              >
                <Download size={14} />
                Tải file đã ký
              </button>
            </div>

            {fileInfo && (
              <div className="mt-3 rounded-lg border border-zinc-800 bg-zinc-900/70 p-3 text-xs text-zinc-300">
                <div>Filename: {fileInfo.name}</div>
                <div>MIME type: {fileInfo.mimeType}</div>
                <div>Size: {formatFileSize(fileInfo.size)}</div>
              </div>
            )}

            {error && (
              <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">
                {error}
              </div>
            )}
            {success && (
              <div className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
                {success}
              </div>
            )}
          </div>

          <div className="rounded-xl border border-zinc-800 bg-zinc-950/60">
            <div className="border-b border-zinc-800 px-4 py-3 text-sm font-medium">
              File đã ký trong phiên này
            </div>
            <div className="max-h-72 overflow-auto">
              {signedFiles.length === 0 ? (
                <div className="px-4 py-6 text-sm text-zinc-400">Chưa có file đã ký.</div>
              ) : (
                signedFiles.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between gap-3 border-b border-zinc-800 px-4 py-3 text-xs last:border-b-0"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm text-zinc-100">{item.filename}</div>
                      <div className="text-zinc-400">
                        {formatFileSize(item.size)} · {item.signed_at}
                      </div>
                      <div className="text-zinc-400">
                        signer: {item.signer} · thuật toán: {item.algorithm} · hash: {item.hash}
                      </div>
                      <div className="text-emerald-300">status: signed</div>
                    </div>
                    <button
                      type="button"
                      onClick={() => downloadSignedContainer(item.container)}
                      className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-1 text-zinc-200 hover:border-blue-500"
                    >
                      <Download size={12} />
                      Tải file đã ký
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

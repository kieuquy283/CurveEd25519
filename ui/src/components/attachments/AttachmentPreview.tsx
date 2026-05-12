"use client";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Attachment, AttachmentCryptoInfo } from "@/types/models";
import { revokePreviewUrl } from "@/services/attachments";
import CryptoTracePanel from "@/components/crypto/CryptoTracePanel";
import { detectSignedFileContainer, verifySignedContainer } from "@/services/signedFile";
import { useAuthStore } from "@/store/useAuthStore";
import { VerificationResult } from "@/types/models";

export default function AttachmentPreview({
  attachment,
}: {
  attachment: Attachment;
}) {
  const url = attachment.localUrl ?? attachment.url;
  const crypto = (
    attachment.crypto ??
    (attachment.metadata?.crypto as AttachmentCryptoInfo | undefined)
  );
  const [openPanel, setOpenPanel] = useState(false);
  const [verifyResult, setVerifyResult] = useState<VerificationResult | null>(null);
  const [verifyResultFor, setVerifyResultFor] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const currentUserEmail = useAuthStore((s) => s.currentUser?.email);
  const signedContainer = useMemo(
    () => detectSignedFileContainer(attachment),
    [attachment]
  );

  useEffect(() => {
    return () => {
      if (attachment.localUrl) revokePreviewUrl(attachment.id);
    };
  }, [attachment]);

  const activeVerifyResult = verifyResultFor === attachment.id ? verifyResult : null;

  const runVerify = useCallback(async () => {
    if (!signedContainer || verifying) return;
    setVerifying(true);
    try {
      const result = await verifySignedContainer(signedContainer, currentUserEmail);
      setVerifyResult(result);
      setVerifyResultFor(attachment.id);
    } catch (err) {
      setVerifyResult({
        ok: false,
        valid: false,
        message: err instanceof Error ? err.message : "Xác minh thất bại.",
      });
      setVerifyResultFor(attachment.id);
    } finally {
      setVerifying(false);
    }
  }, [signedContainer, currentUserEmail, verifying, attachment.id]);

  useEffect(() => {
    if (!signedContainer || activeVerifyResult || verifying) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void runVerify();
  }, [signedContainer, activeVerifyResult, verifying, runVerify]);

  const downloadBase64 = (filename: string, mimeType: string, base64: string) => {
    const link = document.createElement("a");
    link.href = `data:${mimeType};base64,${base64}`;
    link.download = filename;
    link.click();
  };

  if (!url) {
    return (
      <div className="p-3 bg-slate-800 rounded-md text-sm">
        {attachment.fileName}
      </div>
    );
  }

  const isImage = attachment.mimeType.startsWith("image/");
  const isPdf = attachment.mimeType === "application/pdf";

  return (
    <div className="p-2">
      {isImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={url}
          alt={attachment.fileName}
          className="max-h-40 rounded-md"
        />
      ) : isPdf ? (
        <div
          className="p-3 bg-slate-800 rounded-md text-sm cursor-pointer"
          onClick={() => setOpenPanel(true)}
        >
          <div className="font-medium">{attachment.fileName}</div>
          <div className="text-xs text-zinc-400">
            PDF · {Math.round((attachment.size || 0) / 1024)} KB
          </div>
          <a
            className="mt-2 inline-block text-xs text-blue-300 underline"
            href={url}
            download={attachment.fileName}
            onClick={(event) => event.stopPropagation()}
          >
            Open / Download
          </a>
        </div>
      ) : (
        <div className="p-3 bg-slate-800 rounded-md text-sm">
          <div>{attachment.fileName}</div>
          <a
            className="mt-2 inline-block text-xs text-blue-300 underline"
            href={url}
            download={attachment.fileName}
          >
            Open / Download
          </a>
        </div>
      )}

      <div className="mt-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
        <div>Mã hóa: {crypto?.encryption ?? "ChaCha20-Poly1305"}</div>
        <div>Trao đổi khóa: {crypto?.keyExchange ?? "X25519"}</div>
        <div>KDF: {crypto?.kdf ?? "HKDF-SHA256"}</div>
        <div>Chữ ký: {crypto?.signature ?? "Ed25519"}</div>
        <div>Giải mã: {crypto?.decrypted === false ? "Chưa" : "Thành công"}</div>
      </div>

      {openPanel && (
        <CryptoTracePanel
          envelope={
            attachment.envelope ??
            (attachment.metadata?.envelope as Record<string, unknown> | undefined)
          }
          debug={
            attachment.debug ??
            (attachment.metadata?.debug as Record<string, unknown> | undefined)
          }
          onClose={() => setOpenPanel(false)}
        />
      )}

      {signedContainer && (
        <div className="mt-2 rounded-lg border border-blue-500/30 bg-blue-500/10 px-3 py-2 text-xs text-blue-100">
          <div className="font-semibold mb-1">Chữ ký số</div>
          <div>Signer: {signedContainer.signer || "unknown"}</div>
          <div>Signed at: {signedContainer.signed_at || "-"}</div>
          <div>Algorithm: Ed25519</div>
          <div>Hash: SHA-256</div>
          <div>
            Verification:{" "}
            {verifying
              ? "Đang xác minh"
              : activeVerifyResult
                ? activeVerifyResult.valid
                  ? "Hợp lệ"
                  : "Không hợp lệ"
                : "Chưa xác minh"}
          </div>
          {activeVerifyResult?.debug && (
            <div>
              Trusted connection: {(activeVerifyResult.debug.trusted ?? activeVerifyResult.debug.trusted_connection) ? "Có" : "Không"}
            </div>
          )}
          {activeVerifyResult && !activeVerifyResult.valid && (
            <div className="text-red-300 mt-1">{activeVerifyResult.message}</div>
          )}
          <div className="mt-2 flex flex-wrap gap-2">
            {!activeVerifyResult && (
              <button
                type="button"
                onClick={async () => {
                  setVerifying(true);
                  await runVerify();
                }}
                className="rounded border border-blue-400/50 px-2 py-1 text-blue-100"
              >
                Xác minh chữ ký
              </button>
            )}
            <button
              type="button"
              onClick={() =>
                downloadBase64(
                  `${signedContainer.filename}.signed.json`,
                  "application/json",
                  attachment.dataBase64 || attachment.content_b64 || ""
                )
              }
              className="rounded border border-blue-400/50 px-2 py-1 text-blue-100"
            >
              Tải signed container
            </button>
            {activeVerifyResult?.valid && activeVerifyResult.file?.content_b64 && (
              <button
                type="button"
                onClick={() =>
                  downloadBase64(
                    activeVerifyResult.file?.filename || signedContainer.filename,
                    activeVerifyResult.file?.mime_type || signedContainer.mimeType,
                    activeVerifyResult.file?.content_b64 || ""
                  )
                }
                className="rounded border border-emerald-400/50 px-2 py-1 text-emerald-100"
              >
                Tải file gốc
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

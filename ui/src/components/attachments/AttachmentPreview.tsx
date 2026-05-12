"use client";
import React, { useEffect, useState } from "react";
import { Attachment, AttachmentCryptoInfo } from "@/types/models";
import { revokePreviewUrl } from "@/services/attachments";
import CryptoTracePanel from "@/components/crypto/CryptoTracePanel";

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

  useEffect(() => {
    return () => {
      if (attachment.localUrl) revokePreviewUrl(attachment.id);
    };
  }, [attachment]);

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
    </div>
  );
}

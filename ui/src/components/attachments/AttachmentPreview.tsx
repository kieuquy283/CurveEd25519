"use client";
import React, { useEffect, useState } from "react";
import { Attachment } from "@/types/models";
import { revokePreviewUrl } from "@/services/attachments";
import CryptoTracePanel from "@/components/crypto/CryptoTracePanel";

export default function AttachmentPreview({ attachment }: { attachment: Attachment }) {
  // derive url from prop to avoid setState in effect
  const url = attachment.localUrl;

  useEffect(() => {
    return () => {
      if (attachment.localUrl) revokePreviewUrl(attachment.id);
    };
  }, [attachment]);

  if (!url) {
    return (
      <div className="p-3 bg-slate-800 rounded-md text-sm">{attachment.fileName}</div>
    );
  }

  const isImage = attachment.mimeType.startsWith("image/");
  const isPdf = attachment.mimeType === "application/pdf";
  const [openPanel, setOpenPanel] = useState(false);

  return (
    <div className="p-2">
      {isImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt={attachment.fileName} className="max-h-40 rounded-md" />
      ) : isPdf ? (
        <div className="p-3 bg-slate-800 rounded-md text-sm cursor-pointer" onClick={() => setOpenPanel(true)}>
          <div className="font-medium">{attachment.fileName}</div>
          <div className="text-xs text-zinc-400">PDF · {Math.round((attachment.size || 0) / 1024)} KB</div>
        </div>
      ) : (
        <div className="p-3 bg-slate-800 rounded-md text-sm">{attachment.fileName}</div>
      )}

      {openPanel && (
        <CryptoTracePanel
          envelope={attachment.metadata?.envelope}
          debug={attachment.metadata?.debug}
          onClose={() => setOpenPanel(false)}
        />
      )}
    </div>
  );
}

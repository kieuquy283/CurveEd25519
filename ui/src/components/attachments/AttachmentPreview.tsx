"use client";
import React, { useEffect } from "react";
import { Attachment } from "@/types/models";
import { revokePreviewUrl } from "@/services/attachments";

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

  return (
    <div className="p-2">
      {isImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt={attachment.fileName} className="max-h-40 rounded-md" />
      ) : (
        <div className="p-3 bg-slate-800 rounded-md text-sm">{attachment.fileName}</div>
      )}
    </div>
  );
}

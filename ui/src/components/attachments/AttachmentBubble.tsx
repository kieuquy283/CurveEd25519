"use client";
import React from "react";
import { ChatMessage } from "@/types/models";
import { useAttachmentStore } from "@/store/useAttachmentStore";
import AttachmentPreview from "./AttachmentPreview";
import UploadProgress from "./UploadProgress";

export default function AttachmentBubble({ message }: { message: ChatMessage }) {
  const storeAttachments =
    message.attachmentIds
      ?.map((id) => useAttachmentStore.getState().getAttachment(id))
      .filter(Boolean) ?? [];
  const messageAttachments = message.attachments ?? [];
  const fileAttachment =
    message.file && messageAttachments.length === 0
      ? [
          {
            id:
              message.file.id ??
              `${message.id}-file`,
            fileName:
              message.file.fileName ??
              message.file.filename ??
              "attachment",
            mimeType:
              message.file.mimeType ??
              message.file.mime_type ??
              "application/octet-stream",
            size: message.file.size ?? 0,
            url:
              message.file.url ??
              (message.file.dataBase64 || message.file.content_b64
                ? `data:${message.file.mimeType ?? message.file.mime_type ?? "application/octet-stream"};base64,${message.file.dataBase64 ?? message.file.content_b64}`
                : undefined),
            uploaded: true,
            crypto: message.file.crypto,
          },
        ]
      : [];
  const attachments = [
    ...messageAttachments,
    ...fileAttachment,
    ...storeAttachments,
  ];

  if (attachments.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      {attachments.map((a) => {
        if (!a) return null;
        const progress = useAttachmentStore.getState().uploadProgress.get(a.id) ?? (a.uploaded ? 100 : 0);
        return (
          <div key={a.id} className="bg-slate-800 rounded-md p-2">
            <AttachmentPreview attachment={a} />
            {progress < 100 && <div className="mt-2"><UploadProgress progress={progress} /></div>}
          </div>
        );
      })}
    </div>
  );
}

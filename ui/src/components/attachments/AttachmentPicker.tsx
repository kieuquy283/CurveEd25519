"use client";
import React, { useRef } from "react";
import { Paperclip } from "lucide-react";
import { useAttachmentStore } from "@/store/useAttachmentStore";
import { createPreviewUrl, simulateUploadProgress, sendAttachmentMeta } from "@/services/attachments";
import { useChatStore } from "@/store/useChatStore";

export default function AttachmentPicker({ conversationId }: { conversationId: string }) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const addLocalAttachment = useAttachmentStore((s) => s.addLocalAttachment);
  const chatStore = useChatStore.getState();

  const onFile = async (file: File) => {
    const id = `att-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const localUrl = createPreviewUrl(id, file);
    const a = {
      id,
      fileName: file.name,
      mimeType: file.type || "application/octet-stream",
      size: file.size,
      localUrl,
      uploaded: false,
    };

    addLocalAttachment(a);

    // optimistic message containing attachment id
    const messageId = `msg-${Date.now()}-${Math.random()}`;
    const now = new Date().toISOString();
    chatStore.addMessage({
      id: messageId,
      conversationId,
      from: "frontend",
      to: conversationId,
      text: "",
      timestamp: now,
      status: "pending",
      attachmentIds: [id],
    });

    // Send meta packet
    sendAttachmentMeta(a, conversationId).catch((e) => console.error(e));

    // Simulate upload progress
    simulateUploadProgress(id).catch(() => {});
  };

  const onSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) onFile(f);
    e.currentTarget.value = "";
  };

  return (
    <div>
      <input ref={inputRef} type="file" className="hidden" onChange={onSelect} />
      <button
        onClick={() => inputRef.current?.click()}
        className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
      >
        <Paperclip size={20} className="text-zinc-400" />
      </button>
    </div>
  );
}

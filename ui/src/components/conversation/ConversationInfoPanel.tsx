"use client";

import React, { useMemo, useState } from "react";
import { ChevronDown, FileText, Search, ShieldCheck, UserPen, X } from "lucide-react";
import { ChatMessage, Conversation } from "@/types/models";
import { useContactStore } from "@/store/useContactStore";

type ConversationAttachment = {
  id: string;
  name: string;
  type: string;
  size: number;
  timestamp: string;
  disabled?: boolean;
  onOpen?: () => void;
};

interface Props {
  conversation: Conversation;
  currentUser?: { email?: string | null } | null;
  peer?: { email?: string; displayName?: string } | null;
  messages: ChatMessage[];
  attachments: ConversationAttachment[];
  onSearch: (query: string) => void;
  onSearchResultClick: (messageId: string) => void;
  onEditNickname: (nickname: string) => Promise<void> | void;
  onClose?: () => void;
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(value >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

export function ConversationInfoPanel({
  conversation,
  currentUser,
  peer,
  messages,
  attachments,
  onSearch,
  onSearchResultClick,
  onEditNickname,
  onClose,
}: Props) {
  const [openAbout, setOpenAbout] = useState(true);
  const [openCustomize, setOpenCustomize] = useState(true);
  const [openFiles, setOpenFiles] = useState(true);
  const [searchExpanded, setSearchExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [editingNickname, setEditingNickname] = useState(false);
  const [nickname, setNickname] = useState(conversation.peerName || "");

  const isTrusted = useContactStore((s) => s.isTrustedContact(conversation.peerId));

  const filteredMessages = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return [];
    return messages.filter((m) => {
      const textHit = (m.text || "").toLowerCase().includes(q);
      const attachmentHit = (m.attachments || []).some((a) => a.fileName.toLowerCase().includes(q));
      const fileHit = (m.file?.fileName || m.file?.filename || "").toLowerCase().includes(q);
      return textHit || attachmentHit || fileHit;
    });
  }, [messages, searchQuery]);

  const displayName = conversation.peerName || peer?.displayName || conversation.peerId;
  const subtitle = peer?.email || conversation.peerId;
  const avatarLetter = (displayName || "?").charAt(0).toUpperCase();

  return (
    <aside
      className="h-full w-full md:w-[360px] shrink-0 border-l border-[var(--border)] bg-zinc-950 text-zinc-100 overflow-y-auto"
      aria-label="Thông tin cuộc trò chuyện"
    >
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-zinc-800 bg-zinc-950/95 px-4 py-3 backdrop-blur">
        <h3 className="text-sm font-semibold">Thông tin cuộc trò chuyện</h3>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
            aria-label="Đóng thông tin cuộc trò chuyện"
          >
            <X size={16} />
          </button>
        )}
      </div>

      <div className="px-4 py-4">
        <div className="flex flex-col items-center text-center">
          <div className="mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 text-xl font-semibold text-white">
            {avatarLetter}
          </div>
          <div className="text-base font-semibold">{displayName}</div>
          <div className="text-xs text-zinc-400">{subtitle}</div>
          <div className="mt-2 inline-flex items-center gap-1 rounded-full border border-emerald-700/40 bg-emerald-900/20 px-2 py-1 text-xs text-emerald-300">
            <ShieldCheck size={12} />
            <span>{isTrusted ? "Đã xác minh" : "Được mã hóa đầu cuối"}</span>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-3 gap-2">
          <button
            type="button"
            onClick={() => {
              setSearchExpanded(true);
            }}
            className="rounded-lg border border-zinc-800 bg-zinc-900 px-2 py-2 text-xs hover:border-zinc-700"
          >
            <span className="mx-auto mb-1 block w-fit"><Search size={14} /></span>
            Tìm kiếm
          </button>
          <button
            type="button"
            onClick={() => setOpenFiles((v) => !v)}
            className="rounded-lg border border-zinc-800 bg-zinc-900 px-2 py-2 text-xs hover:border-zinc-700"
          >
            <span className="mx-auto mb-1 block w-fit"><FileText size={14} /></span>
            File
          </button>
          <button
            type="button"
            onClick={() => setEditingNickname((v) => !v)}
            className="rounded-lg border border-zinc-800 bg-zinc-900 px-2 py-2 text-xs hover:border-zinc-700"
          >
            <span className="mx-auto mb-1 block w-fit"><UserPen size={14} /></span>
            Biệt danh
          </button>
        </div>

        <Section title="Thông tin về đoạn chat" open={openAbout} onToggle={() => setOpenAbout((v) => !v)}>
          <div className="text-xs text-zinc-400">
            {conversation.isOnline ? "Đang hoạt động" : "Ngoại tuyến"}
            {currentUser?.email ? ` · Bạn: ${currentUser.email}` : ""}
          </div>
        </Section>

        <Section title="Tùy chỉnh đoạn chat" open={openCustomize} onToggle={() => setOpenCustomize((v) => !v)}>
          {editingNickname ? (
            <form
              className="space-y-2"
              onSubmit={async (e) => {
                e.preventDefault();
                await onEditNickname(nickname.trim());
                setEditingNickname(false);
              }}
            >
              <input
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                placeholder="Nhập biệt danh"
                className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-zinc-500"
              />
              <button type="submit" className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500">
                Lưu biệt danh
              </button>
            </form>
          ) : (
            <button
              type="button"
              onClick={() => setEditingNickname(true)}
              className="text-xs text-zinc-300 underline decoration-zinc-600 underline-offset-2"
            >
              Chỉnh sửa biệt danh
            </button>
          )}
        </Section>

        <Section title="File phương tiện và file" open={openFiles} onToggle={() => setOpenFiles((v) => !v)}>
          {attachments.length === 0 ? (
            <div className="text-xs text-zinc-500">Chưa có file trong đoạn chat này.</div>
          ) : (
            <div className="space-y-2">
              {attachments.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  disabled={a.disabled}
                  onClick={() => a.onOpen?.()}
                  className="w-full rounded-lg border border-zinc-800 bg-zinc-900 p-2 text-left text-xs disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <div className="truncate font-medium text-zinc-200">{a.name}</div>
                  <div className="truncate text-zinc-400">{a.type} · {formatBytes(a.size)}</div>
                  <div className="text-zinc-500">{new Date(a.timestamp).toLocaleString()}</div>
                </button>
              ))}
            </div>
          )}
        </Section>

        {searchExpanded && (
          <div className="mt-4 rounded-lg border border-zinc-800 bg-zinc-900 p-3">
            <div className="mb-2 text-xs font-medium text-zinc-200">Tìm trong đoạn chat</div>
            <input
              value={searchQuery}
              onChange={(e) => {
                const q = e.target.value;
                setSearchQuery(q);
                onSearch(q);
              }}
              placeholder="Tìm theo tin nhắn hoặc tên file"
              className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-zinc-500"
            />
            <div className="mt-2 text-xs text-zinc-400">{filteredMessages.length} kết quả</div>
            <div className="mt-2 max-h-52 space-y-1 overflow-y-auto">
              {filteredMessages.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => onSearchResultClick(m.id)}
                  className="w-full rounded border border-zinc-800 px-2 py-1 text-left text-xs hover:border-zinc-700"
                >
                  <div className="truncate text-zinc-200">{m.text || m.file?.fileName || m.file?.filename || "File đính kèm"}</div>
                  <div className="text-zinc-500">{new Date(m.timestamp).toLocaleString()}</div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

function Section({
  title,
  open,
  onToggle,
  children,
}: {
  title: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-4 rounded-lg border border-zinc-800 bg-zinc-900">
      <button type="button" onClick={onToggle} className="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-medium">
        <span>{title}</span>
        <ChevronDown size={16} className={open ? "rotate-180" : ""} />
      </button>
      {open && <div className="border-t border-zinc-800 px-3 py-3">{children}</div>}
    </section>
  );
}


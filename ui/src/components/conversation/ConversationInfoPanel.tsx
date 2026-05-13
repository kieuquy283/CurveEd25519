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
    <aside className="h-full w-full overflow-y-auto rounded-[2rem] border border-white/10 bg-slate-950/70 text-zinc-100 shadow-[0_0_60px_rgba(79,70,229,0.2)] backdrop-blur-xl" aria-label="Thông tin cuộc trò chuyện">
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-white/10 bg-slate-950/85 px-5 py-4 backdrop-blur">
        <h3 className="text-sm font-semibold">Thông tin cuộc trò chuyện</h3>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl p-2 text-zinc-400 hover:bg-white/[0.06] hover:text-zinc-100"
            aria-label="Đóng thông tin cuộc trò chuyện"
          >
            <X size={16} />
          </button>
        )}
      </div>

      <div className="px-4 py-5">
        <div className="px-2 text-center">
          <div className="mx-auto mb-3 flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-blue-500 text-2xl font-semibold text-white ring-4 ring-violet-400/20 shadow-[0_0_40px_rgba(124,58,237,0.28)]">
            {avatarLetter}
          </div>
          <div className="text-base font-semibold">{displayName}</div>
          <div className="text-xs text-zinc-400">{subtitle}</div>
          <div className="mt-2 inline-flex items-center gap-1 rounded-full border border-emerald-700/40 bg-emerald-900/20 px-2 py-1 text-xs text-emerald-300">
            <ShieldCheck size={12} />
            <span>{isTrusted ? "Đã xác minh" : "Tin nhắn được mã hóa đầu cuối"}</span>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-3 gap-3">
          <ActionCard label="Search" onClick={() => setSearchExpanded(true)} icon={<Search size={14} />} />
          <ActionCard label="Files" onClick={() => setOpenFiles((v) => !v)} icon={<FileText size={14} />} />
          <ActionCard label="Edit nickname" onClick={() => setEditingNickname((v) => !v)} icon={<UserPen size={14} />} />
        </div>

        <Section title="Thông tin cuộc trò chuyện" open={openAbout} onToggle={() => setOpenAbout((v) => !v)}>
          <div className="text-xs text-zinc-400">
            {conversation.isOnline ? "Đã kết nối an toàn" : "Mất kết nối"}
            {currentUser?.email ? ` · Bạn: ${currentUser.email}` : ""}
          </div>
        </Section>

        <Section title="Biệt danh" open={openCustomize} onToggle={() => setOpenCustomize((v) => !v)}>
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
                aria-label="Biệt danh"
                className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm outline-none focus:border-violet-400/50"
              />
              <button type="submit" className="rounded-xl bg-gradient-to-r from-violet-600 to-blue-600 px-3 py-1.5 text-xs font-medium text-white">
                Lưu biệt danh
              </button>
            </form>
          ) : (
            <button type="button" onClick={() => setEditingNickname(true)} className="text-xs text-zinc-300 underline decoration-zinc-600 underline-offset-2">
              Chỉnh sửa biệt danh
            </button>
          )}
        </Section>

        <Section title="Tệp đã chia sẻ" open={openFiles} onToggle={() => setOpenFiles((v) => !v)}>
          {attachments.length === 0 ? (
            <div className="text-xs text-zinc-500">Chưa có tệp trong cuộc trò chuyện này.</div>
          ) : (
            <div className="space-y-2">
              {attachments.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  disabled={a.disabled}
                  onClick={() => a.onOpen?.()}
                  className="flex w-full items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-2 text-left text-xs hover:bg-white/[0.06] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium text-zinc-200">{a.name}</div>
                    <div className="truncate text-zinc-400">{a.type} · {formatBytes(a.size)}</div>
                    <div className="text-zinc-500">{new Date(a.timestamp).toLocaleString()}</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </Section>

        {searchExpanded && (
          <div className="mx-1 mt-4 rounded-3xl border border-white/10 bg-white/[0.04] p-4">
            <div className="mb-2 text-xs font-medium text-zinc-200">Search in conversation</div>
            <input
              value={searchQuery}
              onChange={(e) => {
                const q = e.target.value;
                setSearchQuery(q);
                onSearch(q);
              }}
              placeholder="Tìm trong đoạn chat"
              aria-label="Tìm trong đoạn chat"
              className="w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-sm outline-none focus:border-violet-400/50"
            />
            <div className="mt-2 text-xs text-zinc-400">{filteredMessages.length} kết quả</div>
            <div className="mt-2 max-h-52 space-y-1 overflow-y-auto">
              {filteredMessages.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => onSearchResultClick(m.id)}
                  className="w-full rounded-xl border border-white/10 px-2 py-1.5 text-left text-xs hover:bg-white/[0.06]"
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

function ActionCard({ label, onClick, icon }: { label: string; onClick: () => void; icon: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} className="rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-xs text-zinc-300 hover:bg-violet-500/10 hover:text-white">
      <span className="mx-auto mb-1 block w-fit">{icon}</span>
      {label}
    </button>
  );
}

function Section({ title, open, onToggle, children }: { title: string; open: boolean; onToggle: () => void; children: React.ReactNode }) {
  return (
    <section className="mx-1 mb-4 mt-4 rounded-3xl border border-white/10 bg-white/[0.04] p-4">
      <button type="button" onClick={onToggle} className="flex w-full items-center justify-between text-left text-sm font-semibold text-zinc-100">
        <span>{title}</span>
        <ChevronDown size={16} className={open ? "rotate-180" : ""} />
      </button>
      {open && <div className="mt-3 border-t border-white/10 pt-3">{children}</div>}
    </section>
  );
}

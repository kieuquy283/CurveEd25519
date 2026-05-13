"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { Conversation } from "@/types/models";
import {
  FileSignature,
  Plus,
  Settings,
  Shield,
  Search,
  Wifi,
  WifiOff,
  Loader2,
} from "lucide-react";

import { useChatStore } from "@/store/useChatStore";
import { useWebSocketStore } from "@/store/useWebSocketStore";
import { ConversationList } from "@/components/ConversationList";
import StartConversationDialog from "@/components/StartConversationDialog";
import SignatureDialog from "@/components/signature/SignatureDialog";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/useAuthStore";
import { websocketService } from "@/services/websocket";
import { listTrustedContacts, requestConnection, verifyConnection } from "@/services/connections";
import { useContactStore } from "@/store/useContactStore";
import { listConversations, listConversationMessages } from "@/services/conversations";
import { listNotifications, markNotificationRead } from "@/services/notifications";
import { useNotificationStore } from "@/store/useNotificationStore";
import { getNickname } from "@/lib/conversationNicknames";

interface SidebarProps {
  onSelectConversation?: () => void;
}

export function Sidebar({ onSelectConversation }: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [showDialog, setShowDialog] = useState(false);
  const [showSignatureDialog, setShowSignatureDialog] = useState(false);
  const { currentUser, logout } = useAuthStore();
  const replaceContacts = useContactStore((s) => s.replaceContacts);
  const contactMap = useContactStore((s) => s.contacts);
  const trustedContacts = useMemo(
    () => Array.from(contactMap.values()).filter((contact) => contact.trusted),
    [contactMap]
  );
  const [connectTo, setConnectTo] = useState("");
  const [connectionId, setConnectionId] = useState("");
  const [verifyCode, setVerifyCode] = useState("");
  const [connectionMsg, setConnectionMsg] = useState("");
  const [devCode, setDevCode] = useState("");
  const loadedConversationsForUserRef = useRef<string | null>(null);
  const loadedMessagesForKeyRef = useRef<string | null>(null);

  const conversationMap = useChatStore((s) => s.conversations);
  const addConversation = useChatStore((s) => s.addConversation);
  const addMessages = useChatStore((s) => s.addMessages);
  const setActiveConversation = useChatStore((s) => s.setActiveConversation);
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const notificationStateHistory = useNotificationStore((s) => s.history);
  const upsertNotification = useNotificationStore((s) => s.upsertNotification);
  const markAsReadLocal = useNotificationStore((s) => s.markAsRead);

  const connected = useWebSocketStore((s) => s.connected);
  const connecting = useWebSocketStore((s) => s.connecting);
  const error = useWebSocketStore((s) => s.error);
  const reconnectAttempts = useWebSocketStore((s) => s.reconnectAttempts);

  const conversations = useMemo(
    () =>
      Array.from(conversationMap.values()).sort(
        (a, b) =>
          new Date(b.lastMessageAt || b.createdAt).getTime() -
          new Date(a.lastMessageAt || a.createdAt).getTime()
      ),
    [conversationMap]
  );

  const filtered = conversations.filter((c) =>
    (c.peerName ?? c.peerId).toLowerCase().includes(searchQuery.toLowerCase())
  );
  const notificationHistory = useMemo(
    () => [...notificationStateHistory].reverse().slice(0, 10),
    [notificationStateHistory]
  );

  useEffect(() => {
    const userId = currentUser?.id;
    if (!userId) return;

    listTrustedContacts(userId)
      .then((result) => {
        const contacts = result.contacts.map((item) => ({
          id: item.user_id || item.email,
          connectionId: item.connection_id,
          name: item.display_name || item.email,
          peerId: item.user_id || item.email,
          trustLevel: item.trusted ? ("verified" as const) : ("untrusted" as const),
          trusted: item.trusted,
          keyChanged: Boolean(item.key_changed),
          isOnline: false,
          createdAt: item.verified_at || new Date().toISOString(),
          verifiedAt: item.verified_at,
          fingerprint: item.key_fingerprint,
          ed25519PublicKey: item.ed25519_public_key,
          x25519PublicKey: item.x25519_public_key,
        }));
        replaceContacts(contacts);
      })
      .catch(() => {});
  }, [currentUser?.id, replaceContacts]);

  useEffect(() => {
    const userId = currentUser?.id || currentUser?.email;
    if (!userId) return;
    if (loadedConversationsForUserRef.current === userId) return;
    loadedConversationsForUserRef.current = userId;
    listConversations(userId)
      .then((result) => {
        for (const row of result.conversations) {
          const a = String(row.user_a_email || "");
          const b = String(row.user_b_email || "");
          const me = String(userId).toLowerCase();
          const peer = String(row.peer_email || (a.toLowerCase() === me ? b : a));
          const metadata = row.metadata && typeof row.metadata === "object" ? (row.metadata as Record<string, unknown>) : {};
          const nicknameMap = metadata.nicknames && typeof metadata.nicknames === "object" ? (metadata.nicknames as Record<string, unknown>) : {};
          const byUser = nicknameMap[me] && typeof nicknameMap[me] === "object" ? (nicknameMap[me] as Record<string, unknown>) : {};
          const serverNickname = String(byUser[String(peer).toLowerCase()] || "");
          const localNickname = getNickname(userId, peer) || "";
          const peerName = localNickname || serverNickname || String(row.peer_display_name || peer);
          if (!peer) continue;
          addConversation({
            id: String(row.id || `${me}:${peer}`),
            peerId: peer,
            peerName,
            createdAt: String(row.created_at || new Date().toISOString()),
            lastMessageAt: String(row.last_message_at || row.updated_at || row.created_at || new Date().toISOString()),
            unreadCount: 0,
            encrypted: true,
          });
        }
      })
      .catch((fetchError) => {
        console.warn("[Sidebar] Failed to fetch conversations:", fetchError);
        loadedConversationsForUserRef.current = null;
      });
  }, [currentUser?.id, currentUser?.email, addConversation]);

  useEffect(() => {
    const userId = currentUser?.id || currentUser?.email;
    if (!userId) return;
    let mounted = true;
    const pull = async () => {
      try {
        const res = await listNotifications(userId);
        if (!mounted) return;
        for (const n of res.notifications) {
          const createdAtRaw = String(n.created_at || "");
          const createdAt = Number.isNaN(Date.parse(createdAtRaw)) ? Date.now() : Date.parse(createdAtRaw);
          upsertNotification({
            id: String(n.id || crypto.randomUUID()),
            title: String(n.title || "Thông báo"),
            body: String(n.body || ""),
            level: String(n.type || "info") === "message" ? "message" : "info",
            read: Boolean(n.read),
            dismissed: false,
            createdAt,
            metadata: (n.data as Record<string, unknown> | undefined) || undefined,
          });
        }
      } catch {
        // ignore
      }
    };
    pull();
    const id = setInterval(pull, 15000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, [currentUser?.id, currentUser?.email, upsertNotification]);

  useEffect(() => {
    const userId = currentUser?.id || currentUser?.email;
    if (!userId || !activeConversationId) return;
    const key = `${userId}::${activeConversationId}`;
    if (loadedMessagesForKeyRef.current === key) return;
    loadedMessagesForKeyRef.current = key;
    listConversationMessages(activeConversationId, userId, 100)
      .then((result) => {
        const mapped = result.messages.map((m) => ({
          id: String(m.id || m.packet_id || crypto.randomUUID()),
          packetId: (m.packet_id as string | undefined) || undefined,
          conversationId: String(m.conversation_id || activeConversationId),
          from: String(m.sender_email || ""),
          to: String(m.receiver_email || ""),
          text: String(m.plaintext_preview || ""),
          type: String(m.message_type || "text") as "text" | "file",
          envelope: (m.ciphertext_envelope as Record<string, unknown> | undefined) || undefined,
          attachments: m.attachment_json && typeof m.attachment_json === "object" ? [m.attachment_json as never] : undefined,
          cryptoDebug: (m.crypto_debug as Record<string, unknown> | undefined) || undefined,
          timestamp: String(m.created_at || new Date().toISOString()),
          status: String(m.status || "delivered") as
            | "pending"
            | "queued"
            | "sent"
            | "delivered"
            | "acked"
            | "read"
            | "failed"
            | "expired"
            | "dropped",
        }));
        addMessages(mapped);
      })
      .catch((fetchError) => {
        console.warn("[Sidebar] Failed to fetch messages:", fetchError);
        loadedMessagesForKeyRef.current = null;
      });
  }, [activeConversationId, currentUser?.id, currentUser?.email, addMessages]);

  const handleCreateConversation = (contact: { id: string; name: string }) => {
    const now = new Date().toISOString();
    const conversation: Conversation = {
      id: contact.id,
      peerId: contact.id,
      peerName: contact.name,
      createdAt: now,
      lastMessageAt: now,
      encrypted: true,
      unreadCount: 0,
    };

    addConversation(conversation);
    setActiveConversation(conversation.id);
    onSelectConversation?.();
  };

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/10 px-5 pb-4 pt-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 via-blue-500 to-cyan-400 shadow-[0_0_30px_rgba(99,102,241,0.45)]">
              <Shield size={15} className="text-white" strokeWidth={2.5} />
            </div>

            <div>
              <h1 className="text-sm font-semibold leading-tight text-zinc-100">CurveApp</h1>
              <p className="text-[10px] leading-none text-zinc-400">Secure Messenger</p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setShowDialog(true)}
              className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] transition-colors hover:bg-violet-500/15"
              title="New encrypted conversation"
              type="button"
              aria-label="Tạo cuộc trò chuyện mới"
            >
              <Plus size={16} className="text-violet-200" />
            </button>

            <button
              onClick={() => setShowSignatureDialog(true)}
              className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] transition-colors hover:bg-violet-500/15"
              title="Ký file"
              type="button"
              aria-label="Ký file"
            >
              <FileSignature size={16} className="text-violet-200" />
            </button>

            <button
              className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] transition-colors hover:bg-violet-500/15"
              title="Settings"
              type="button"
              aria-label="Cài đặt"
            >
              <Settings size={16} className="text-violet-200" />
            </button>
          </div>
        </div>

        <ConnectionPill connected={connected} connecting={connecting} error={error} attempts={reconnectAttempts} />
      </div>

      <div className="border-b border-white/10 px-4 py-3">
        <label className="sr-only" htmlFor="conversation-search">Tìm kiếm cuộc trò chuyện</label>
        <div className="relative rounded-2xl border border-white/10 bg-white/[0.04] focus-within:border-violet-400/60 focus-within:ring-2 focus-within:ring-violet-500/20">
          <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            id="conversation-search"
            type="search"
            placeholder="Tìm kiếm cuộc trò chuyện"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={cn(
              "h-10 w-full rounded-2xl bg-transparent pl-8 pr-3 text-sm",
              "text-zinc-100 placeholder:text-zinc-500",
              "focus:outline-none"
            )}
          />
        </div>
        <div className="mt-3 grid grid-cols-4 rounded-2xl border border-white/10 bg-white/[0.03] p-1 text-xs">
          <button type="button" className="rounded-xl bg-white/10 px-2 py-1.5 text-white">All</button>
          <button type="button" className="rounded-xl px-2 py-1.5 text-zinc-400 hover:text-white">Unread</button>
          <button type="button" className="rounded-xl px-2 py-1.5 text-zinc-400 hover:text-white">Groups</button>
          <button type="button" className="rounded-xl px-2 py-1.5 text-zinc-400 hover:text-white">Contacts</button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <ConversationList conversations={filtered} onSelect={onSelectConversation} />
      </div>

      <div className="border-t border-white/10 px-4 py-4">
        <div className="mb-2">
          <div className="mb-1 text-[10px] text-zinc-500">Notifications</div>
          <div className="max-h-24 space-y-1 overflow-auto">
            {notificationHistory.slice(0, 3).map((n) => (
              <button
                key={n.id}
                type="button"
                onClick={async () => {
                  markAsReadLocal(n.id);
                  await markNotificationRead(n.id).catch(() => {});
                  const meta = (n.metadata || {}) as Record<string, unknown>;
                  const peerEmail = String(meta.peerEmail || n.peerId || "");
                  const peerDisplayName = String(meta.peerDisplayName || peerEmail || "");
                  if (!peerEmail) return;
                  const convId = String(meta.conversationId || "");
                  addConversation({
                    id: convId || peerEmail,
                    peerId: peerEmail,
                    peerName: peerDisplayName || peerEmail,
                    createdAt: new Date().toISOString(),
                    lastMessageAt: new Date().toISOString(),
                    unreadCount: 0,
                    encrypted: true,
                  });
                  setActiveConversation(convId || peerEmail);
                  if (String(meta.status || "") === "pending") {
                    setShowDialog(true);
                    setConnectTo(peerEmail);
                    setConnectionId(String(meta.connectionId || ""));
                  }
                  onSelectConversation?.();
                }}
                className="w-full rounded-2xl border border-white/10 bg-white/[0.04] px-2.5 py-2 text-left text-[10px] text-zinc-300 hover:bg-white/[0.08]"
              >
                <div className="font-medium text-zinc-200">{n.title}</div>
                <div className="truncate">{n.body}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="mb-3 rounded-2xl border border-violet-400/20 bg-violet-500/10 p-2 text-[10px] text-violet-200">
          Tin nhắn được mã hóa đầu cuối · Verified contacts: {trustedContacts.length}
        </div>

        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-blue-500 text-xs font-bold text-white">Y</div>

          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium text-zinc-100">{currentUser?.displayName || "You"}</p>
            <p className="truncate text-[10px] text-zinc-400">{currentUser?.email || "Local peer"}</p>
          </div>

          <button
            type="button"
            onClick={logout}
            className="rounded-xl border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-[10px] text-zinc-200 hover:bg-white/[0.08]"
          >
            Logout
          </button>
        </div>
      </div>

      <StartConversationDialog
        open={showDialog}
        onClose={() => setShowDialog(false)}
        trustedContacts={trustedContacts.map((contact) => ({
          id: contact.id,
          name: contact.name,
          peerId: contact.peerId,
          fingerprint: contact.fingerprint,
          trusted: contact.trusted,
        }))}
        onCreate={handleCreateConversation}
        connectTo={connectTo}
        setConnectTo={setConnectTo}
        connectionId={connectionId}
        setConnectionId={setConnectionId}
        verifyCode={verifyCode}
        setVerifyCode={setVerifyCode}
        connectionMsg={connectionMsg}
        devCode={devCode}
        onSendRequest={async () => {
          if (!currentUser?.id || !connectTo.trim()) return;
          try {
            const result = await requestConnection({
              from_user: currentUser.id,
              to: connectTo.trim(),
            });
            setConnectionMsg(`${result.message} (${result.connection_id})`);
            setConnectionId(result.connection_id ?? "");
            setDevCode(result.dev_code ?? "");
          } catch (requestError) {
            setConnectionMsg(requestError instanceof Error ? requestError.message : "Request failed");
          }
        }}
        onVerifyConnection={async () => {
          if (!currentUser?.id || !connectionId.trim() || !verifyCode.trim()) return false;
          try {
            await verifyConnection({
              connection_id: connectionId.trim(),
              user: currentUser.id,
              code: verifyCode.trim(),
            });
            setConnectionMsg("Connection verified");
            const result = await listTrustedContacts(currentUser.id);
            replaceContacts(
              result.contacts.map((item) => ({
                id: item.user_id || item.email,
                connectionId: item.connection_id,
                name: item.display_name || item.email,
                peerId: item.user_id || item.email,
                trustLevel: item.trusted ? ("verified" as const) : ("untrusted" as const),
                trusted: item.trusted,
                keyChanged: Boolean(item.key_changed),
                isOnline: false,
                createdAt: item.verified_at || new Date().toISOString(),
                verifiedAt: item.verified_at,
                fingerprint: item.key_fingerprint,
                ed25519PublicKey: item.ed25519_public_key,
                x25519PublicKey: item.x25519_public_key,
              }))
            );
            return true;
          } catch (verifyError) {
            setConnectionMsg(verifyError instanceof Error ? verifyError.message : "Verify failed");
            return false;
          }
        }}
      />
      <SignatureDialog open={showSignatureDialog} onClose={() => setShowSignatureDialog(false)} />
    </div>
  );
}

interface ConnectionPillProps {
  connected: boolean;
  connecting: boolean;
  error: string | null;
  attempts: number;
}

function ConnectionPill({ connected, connecting, error, attempts }: ConnectionPillProps) {
  if (connected) {
    return (
      <div className="flex items-center gap-1.5 rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1.5">
        <Wifi size={11} className="text-emerald-300" />
        <span className="text-[10px] font-medium text-emerald-300">Đã kết nối an toàn</span>
      </div>
    );
  }

  if (connecting) {
    return (
      <div className="flex items-center gap-1.5 rounded-xl border border-amber-500/25 bg-amber-500/10 px-2.5 py-1.5">
        <Loader2 size={11} className="animate-spin text-amber-300" />
        <span className="text-[10px] font-medium text-amber-300">Đang kết nối...</span>
      </div>
    );
  }

  if (error || attempts > 0) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-red-500/25 bg-red-500/10 px-2.5 py-1.5">
        <WifiOff size={11} className="shrink-0 text-red-300" />
        <span className="truncate text-[10px] font-medium text-red-300">{attempts > 0 ? `Đang kết nối lại... (${attempts})` : "Mất kết nối"}</span>
        <button
          type="button"
          onClick={() => {
            websocketService.connect().catch(() => {});
          }}
          className="ml-auto rounded-lg border border-red-400/40 px-1.5 py-0.5 text-[10px] text-red-100 hover:bg-red-500/20"
        >
          Kết nối lại
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.04] px-2.5 py-1.5">
      <WifiOff size={11} className="text-zinc-400" />
      <span className="text-[10px] text-zinc-400">Mất kết nối</span>
    </div>
  );
}

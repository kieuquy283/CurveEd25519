/**
 * Sidebar â€” conversation list, search, connection status, profile.
 */

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
  const [showSignatureDialog, setShowSignatureDialog] =
    useState(false);
  const { currentUser, logout } = useAuthStore();
  const replaceContacts = useContactStore((s) => s.replaceContacts);
  const contactMap = useContactStore((s) => s.contacts);
  const trustedContacts = useMemo(
    () =>
      Array.from(contactMap.values()).filter(
        (contact) => contact.trusted
      ),
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
          const metadata = (row.metadata && typeof row.metadata === "object")
            ? (row.metadata as Record<string, unknown>)
            : {};
          const nicknameMap = (metadata.nicknames && typeof metadata.nicknames === "object")
            ? (metadata.nicknames as Record<string, unknown>)
            : {};
          const byUser = (nicknameMap[me] && typeof nicknameMap[me] === "object")
            ? (nicknameMap[me] as Record<string, unknown>)
            : {};
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
      .catch((error) => {
        console.warn("[Sidebar] Failed to fetch conversations:", error);
        loadedConversationsForUserRef.current = null;
      });
  }, [currentUser?.id, currentUser?.email, addConversation]);

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
          type: (String(m.message_type || "text") as "text" | "file"),
          envelope: (m.ciphertext_envelope as Record<string, unknown> | undefined) || undefined,
          attachments:
            m.attachment_json && typeof m.attachment_json === "object"
              ? [m.attachment_json as never]
              : undefined,
          cryptoDebug: (m.crypto_debug as Record<string, unknown> | undefined) || undefined,
          timestamp: String(m.created_at || new Date().toISOString()),
          status: (String(m.status || "delivered") as "pending" | "queued" | "sent" | "delivered" | "acked" | "read" | "failed" | "expired" | "dropped"),
        }));
        addMessages(mapped);
      })
      .catch((error) => {
        console.warn("[Sidebar] Failed to fetch messages:", error);
        loadedMessagesForKeyRef.current = null;
      });
  }, [activeConversationId, currentUser?.id, currentUser?.email, addMessages]);

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
            level: (String(n.type || "info") === "message" ? "message" : "info"),
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
    <div className="flex flex-col h-full">
      <div className="px-4 pt-4 pb-3 border-b border-[var(--border)]">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center shadow-lg glow-primary">
              <Shield size={15} className="text-white" strokeWidth={2.5} />
            </div>

            <div>
              <h1 className="text-sm font-semibold leading-tight text-foreground">
                CurveApp
              </h1>
              <p className="text-[10px] text-muted-foreground leading-none">
                Secure Messenger
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowDialog(true)}
              className="w-8 h-8 rounded-lg hover:bg-white/5 flex items-center justify-center transition-colors"
              title="New encrypted conversation"
              type="button"
            >
              <Plus size={16} className="text-muted-foreground" />
            </button>

            <button
              onClick={() =>
                setShowSignatureDialog(true)
              }
              className="w-8 h-8 rounded-lg hover:bg-white/5 flex items-center justify-center transition-colors"
              title="Ký file"
              type="button"
            >
              <FileSignature
                size={16}
                className="text-muted-foreground"
              />
            </button>

            <button
              className="w-8 h-8 rounded-lg hover:bg-white/5 flex items-center justify-center transition-colors"
              title="Settings"
              type="button"
            >
              <Settings size={16} className="text-muted-foreground" />
            </button>
          </div>
        </div>

        <ConnectionPill
          connected={connected}
          connecting={connecting}
          error={error}
          attempts={reconnectAttempts}
        />
      </div>

      <div className="px-3 py-2 border-b border-[var(--border)]">
        <div className="relative">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
          />

          <input
            type="search"
            placeholder="Tìm kiếm cuộc trò chuyện..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={cn(
              "w-full h-8 pl-8 pr-3 rounded-lg text-sm",
              "bg-white/5 border border-[var(--border)]",
              "text-foreground placeholder:text-muted-foreground",
              "focus:outline-none focus:border-[var(--primary)]/60 focus:bg-white/8",
              "transition-colors"
            )}
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        <ConversationList
          conversations={filtered}
          onSelect={onSelectConversation}
        />
      </div>

      <div className="px-3 py-3 border-t border-[var(--border)]">
        <div className="mb-2">
          <div className="text-[10px] text-zinc-500 mb-1">Notifications</div>
          <div className="max-h-24 overflow-auto space-y-1">
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
                className="w-full rounded border border-zinc-800 bg-zinc-900 px-2 py-1 text-left text-[10px] text-zinc-300 hover:border-zinc-600"
              >
                <div className="font-medium text-zinc-200">{n.title}</div>
                <div className="truncate">{n.body}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="mb-3 text-[10px] text-zinc-500">Verified contacts: {trustedContacts.length}</div>

        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-pink-500 flex items-center justify-center text-xs font-bold text-white">
            Y
          </div>

          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-foreground truncate">
              {currentUser?.displayName || "You"}
            </p>
            <p className="text-[10px] text-muted-foreground truncate">
              {currentUser?.email || "Local peer"}
            </p>
          </div>

          <button
            type="button"
            onClick={logout}
            className="rounded-md border border-zinc-700 px-2 py-1 text-[10px] text-zinc-300 hover:border-zinc-500 hover:text-zinc-100"
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
          } catch (error) {
            setConnectionMsg(error instanceof Error ? error.message : "Request failed");
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
          } catch (error) {
            setConnectionMsg(error instanceof Error ? error.message : "Verify failed");
            return false;
          }
        }}
      />
      <SignatureDialog
        open={showSignatureDialog}
        onClose={() =>
          setShowSignatureDialog(false)
        }
      />
    </div>
  );
}

interface ConnectionPillProps {
  connected: boolean;
  connecting: boolean;
  error: string | null;
  attempts: number;
}

function ConnectionPill({
  connected,
  connecting,
  error,
  attempts,
}: ConnectionPillProps) {
  if (connected) {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-green-500/10 border border-green-500/20">
        <Wifi size={11} className="text-green-400" />
        <span className="text-[10px] font-medium text-green-400">
          Đã kết nối
        </span>
      </div>
    );
  }

  if (connecting) {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-yellow-500/10 border border-yellow-500/20">
        <Loader2 size={11} className="text-yellow-400 animate-spin" />
        <span className="text-[10px] font-medium text-yellow-400">
          Đang kết nối...
        </span>
      </div>
    );
  }

  if (error || attempts > 0) {
    return (
      <div className="flex items-center gap-2 px-2 py-1 rounded-md bg-red-500/10 border border-red-500/20">
        <WifiOff size={11} className="text-red-400 shrink-0" />
        <span className="text-[10px] font-medium text-red-400 truncate">
          {attempts > 0 ? `Đang kết nối lại... (${attempts})` : "Mất kết nối"}
        </span>
        <button
          type="button"
          onClick={() => {
            websocketService.connect().catch(() => {});
          }}
          className="ml-auto rounded border border-red-400/40 px-1.5 py-0.5 text-[10px] text-red-200 hover:bg-red-500/20"
        >
          Kết nối lại
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-white/5 border border-[var(--border)]">
      <WifiOff size={11} className="text-muted-foreground" />
      <span className="text-[10px] text-muted-foreground">Mất kết nối</span>
    </div>
  );
}



/**
 * Sidebar — conversation list, search, connection status, profile.
 */

"use client";

import React, { useEffect, useMemo, useState } from "react";
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

  const conversationMap = useChatStore((s) => s.conversations);
  const addConversation = useChatStore((s) => s.addConversation);
  const setActiveConversation = useChatStore((s) => s.setActiveConversation);

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
            placeholder="Search conversations…"
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
          Connected
        </span>
      </div>
    );
  }

  if (connecting) {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-yellow-500/10 border border-yellow-500/20">
        <Loader2 size={11} className="text-yellow-400 animate-spin" />
        <span className="text-[10px] font-medium text-yellow-400">
          Connecting…
        </span>
      </div>
    );
  }

  if (error || attempts > 0) {
    return (
      <div className="flex items-center gap-2 px-2 py-1 rounded-md bg-red-500/10 border border-red-500/20">
        <WifiOff size={11} className="text-red-400 shrink-0" />
        <span className="text-[10px] font-medium text-red-400 truncate">
          {attempts > 0 ? `Reconnecting… (${attempts})` : "Disconnected"}
        </span>
        <button
          type="button"
          onClick={() => {
            websocketService.connect().catch(() => {});
          }}
          className="ml-auto rounded border border-red-400/40 px-1.5 py-0.5 text-[10px] text-red-200 hover:bg-red-500/20"
        >
          Reconnect now
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-white/5 border border-[var(--border)]">
      <WifiOff size={11} className="text-muted-foreground" />
      <span className="text-[10px] text-muted-foreground">Offline</span>
    </div>
  );
}

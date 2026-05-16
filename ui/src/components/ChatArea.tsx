"use client";

import { useEffect, useMemo, useState } from "react";

import { useChatStore } from "@/store/useChatStore";
import { useAuthStore } from "@/store/useAuthStore";

import { MessageList } from "@/components/MessageList";
import { MessageComposer } from "@/components/MessageComposer";
import { ChatHeader } from "@/components/ChatHeader";
import { ChatMessage } from "@/types/models";
import { ConversationInfoPanel } from "@/components/conversation/ConversationInfoPanel";
import { patchConversationMetadata } from "@/services/conversations";
import { getNickname, setNickname } from "@/lib/conversationNicknames";
import DynamicWatermark from "@/components/privacy/DynamicWatermark";
import { useSettingsStore } from "@/store/useSettingsStore";
import VerifyConnectionRequiredModal from "@/components/connection/VerifyConnectionRequiredModal";
import { ConnectionStatusResponse, normalizeEmail } from "@/services/connections";
import { useConnectionStatusStore } from "@/store/useConnectionStatusStore";
import { useCameraGuardStore } from "@/store/useCameraGuardStore";

interface ChatAreaProps {
  conversationId: string;
  onBack?: () => void;
  onActivateShield?: () => void;
}

const EMPTY_MESSAGES: ChatMessage[] = [];

export function ChatArea({ conversationId, onBack, onActivateShield }: ChatAreaProps) {
  const [infoPanelOpen, setInfoPanelOpen] = useState(false);
  const [highlightedMessageId, setHighlightedMessageId] = useState<string | null>(null);
  const conversations = useChatStore((s) => s.conversations);
  const updateConversation = useChatStore((s) => s.updateConversation);
  const currentUser = useAuthStore((s) => s.currentUser);
  const prefs = useSettingsStore((s) => s.prefs);
  const [connectionStatusOpen, setConnectionStatusOpen] = useState(false);
  const refreshConnectionStatus = useConnectionStatusStore((s) => s.refreshConnectionStatus);
  const getConnectionStatusForPair = useConnectionStatusStore((s) => s.getConnectionStatusForPair);
  const loadingByPair = useConnectionStatusStore((s) => s.loadingByPair);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatusResponse | null>(null);
  const guardEnabled = useCameraGuardStore((s) => s.enabled);
  const captureThreat = useCameraGuardStore((s) => s.threat);

  const activeConversation = conversations.get(conversationId);
  const messages = useChatStore((s) => s.messages.get(conversationId) ?? EMPTY_MESSAGES);

  useEffect(() => {
    if (!activeConversation || !currentUser?.email) return;
    const nick = getNickname(currentUser.email, activeConversation.peerId);
    if (nick && nick !== activeConversation.peerName) {
      updateConversation(activeConversation.id, { peerName: nick });
    }
  }, [activeConversation, currentUser?.email, updateConversation]);

  useEffect(() => {
    if (!activeConversation) return;
    const active = activeConversation;
    const user = normalizeEmail(currentUser?.email || currentUser?.id || "");
    const peer = normalizeEmail(active.peerId || "");
    if (!user || !peer) return;
    const cached = getConnectionStatusForPair(user, peer);
    if (cached) setConnectionStatus(cached);
    refreshConnectionStatus(user, peer)
      .then((status) => {
        setConnectionStatus(status);
        const canonicalPeer = normalizeEmail(status.peer?.email || active.peerId);
        updateConversation(active.id, {
          peerId: canonicalPeer || active.peerId,
          peerName: status.peer?.display_name || active.peerName,
        });
      })
      .catch(() => {
        if (!cached) setConnectionStatus(null);
      });
  }, [
    activeConversation?.id,
    activeConversation?.peerId,
    activeConversation?.peerName,
    currentUser?.email,
    currentUser?.id,
    getConnectionStatusForPair,
    refreshConnectionStatus,
    updateConversation,
  ]);

  const attachments = useMemo(() => {
    return messages.flatMap((m) => {
      const direct = (m.attachments || []).map((a) => ({
        id: `${m.id}-${a.id}`,
        name: a.fileName,
        type: a.mimeType,
        size: a.size || 0,
        timestamp: m.timestamp,
        disabled: !(a.url || a.content_b64 || a.dataBase64),
        onOpen: () => {
          if (a.url) window.open(a.url, "_blank", "noopener,noreferrer");
        },
      }));
      const fromFile = m.file
        ? [
            {
              id: `${m.id}-file`,
              name: m.file.fileName || m.file.filename || "attachment",
              type: m.file.mimeType || m.file.mime_type || "application/octet-stream",
              size: m.file.size || 0,
              timestamp: m.timestamp,
              disabled: !(m.file.url || m.file.content_b64 || m.file.dataBase64),
              onOpen: () => {
                if (m.file?.url) window.open(m.file.url, "_blank", "noopener,noreferrer");
              },
            },
          ]
        : [];
      return [...direct, ...fromFile];
    });
  }, [messages]);

  if (!activeConversation) {
    return <div className="flex h-full items-center justify-center text-sm text-zinc-500">Conversation not found</div>;
  }

  const loadingStatus = (() => {
    if (!activeConversation) return false;
    const user = normalizeEmail(currentUser?.email || currentUser?.id || "");
    const peer = normalizeEmail(activeConversation.peerId || "");
    const key = [user, peer].sort().join("::");
    return Boolean(loadingByPair[key]);
  })();

  const applyStatus = (status: ConnectionStatusResponse) => {
    if (!activeConversation) {
      setConnectionStatus(status);
      return;
    }
    setConnectionStatus(status);
    const canonicalPeer = normalizeEmail(status.peer?.email || activeConversation.peerId);
    updateConversation(activeConversation.id, {
      peerId: canonicalPeer || activeConversation.peerId,
      peerName: status.peer?.display_name || activeConversation.peerName,
    });
  };

  return (
    <div className="flex h-full min-w-0 gap-3 lg:gap-4">
      <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden rounded-[2rem] border border-white/10 bg-slate-950/45 backdrop-blur-xl">
        <ChatHeader
          conversation={activeConversation}
          onBack={onBack}
          infoPanelOpen={infoPanelOpen}
          onToggleInfoPanel={() => setInfoPanelOpen((v) => !v)}
          connectionStatusLabel={
            loadingStatus
              ? "Đang kiểm tra kết nối..."
              : connectionStatus?.reason === "verified_connection"
              ? "Đã kết nối an toàn"
              : connectionStatus?.reason === "pending_connection"
                ? "Đang chờ xác minh"
                : connectionStatus?.reason
                  ? "Chưa kết nối"
                  : "Không kiểm tra được kết nối"
          }
          onOpenConnectionSecurity={() => setConnectionStatusOpen(true)}
          onActivateShield={onActivateShield}
        />

        <div className="mx-auto mt-4 max-w-md rounded-3xl border border-violet-400/20 bg-violet-500/10 px-5 py-3 text-center text-sm text-zinc-300 shadow-[0_0_40px_rgba(124,58,237,0.18)] backdrop-blur">
          Tin nhắn được mã hóa đầu cuối
        </div>

        <DynamicWatermark
          enabled={prefs.watermarkEnabled}
          userEmail={currentUser?.email || undefined}
          userId={currentUser?.id || undefined}
          conversationId={activeConversation.id}
          peerName={activeConversation.peerName}
          peerEmail={activeConversation.peerId}
        />

        <div className={guardEnabled && captureThreat.active && captureThreat.level === "high" ? "relative blur-sm" : "relative"}>
          <MessageList messages={messages} conversationId={conversationId} highlightedMessageId={highlightedMessageId} />
        </div>

        <MessageComposer
          conversationId={conversationId}
          peerIdentifier={activeConversation.peerId}
          connectionStatus={connectionStatus}
          onConnectionStatusChange={applyStatus}
          onOpenConnectionStatusModal={() => setConnectionStatusOpen(true)}
          refreshConnectionStatus={refreshConnectionStatus}
        />
      </div>
      <VerifyConnectionRequiredModal
        open={connectionStatusOpen}
        onClose={() => setConnectionStatusOpen(false)}
        status={connectionStatus}
        currentUser={(currentUser?.email || currentUser?.id || "").trim().toLowerCase()}
        peerIdentifier={activeConversation.peerId}
        onStatusRefresh={applyStatus}
        onVerified={applyStatus}
        refreshStatus={refreshConnectionStatus}
      />

      {infoPanelOpen && (
        <>
          <div className="hidden md:block">
            <ConversationInfoPanel
              conversation={activeConversation}
              currentUser={currentUser}
              peer={{ email: activeConversation.peerId, displayName: activeConversation.peerName }}
              messages={messages}
              attachments={attachments}
              onSearch={() => {}}
              onSearchResultClick={(messageId) => {
                setHighlightedMessageId(messageId);
                const el = document.getElementById(`msg-${messageId}`);
                el?.scrollIntoView({ behavior: "smooth", block: "center" });
              }}
              onEditNickname={async (nickname) => {
                const name = nickname || activeConversation.peerId;
                updateConversation(activeConversation.id, { peerName: name });
                if (currentUser?.email) {
                  setNickname(currentUser.email, activeConversation.peerId, name);
                  try {
                    await patchConversationMetadata(activeConversation.id, {
                      user: currentUser.email,
                      metadata_patch: {
                        nicknames: {
                          [currentUser.email.toLowerCase()]: {
                            [activeConversation.peerId.toLowerCase()]: name,
                          },
                        },
                      },
                    });
                  } catch {
                    // local nickname is already persisted
                  }
                }
              }}
            />
          </div>
          <div className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden" onClick={() => setInfoPanelOpen(false)} aria-hidden />
          <div className="fixed inset-y-0 right-0 z-50 w-[92vw] max-w-[380px] md:hidden">
            <ConversationInfoPanel
              conversation={activeConversation}
              currentUser={currentUser}
              peer={{ email: activeConversation.peerId, displayName: activeConversation.peerName }}
              messages={messages}
              attachments={attachments}
              onSearch={() => {}}
              onSearchResultClick={(messageId) => {
                setHighlightedMessageId(messageId);
                const el = document.getElementById(`msg-${messageId}`);
                el?.scrollIntoView({ behavior: "smooth", block: "center" });
                setInfoPanelOpen(false);
              }}
              onEditNickname={async (nickname) => {
                const name = nickname || activeConversation.peerId;
                updateConversation(activeConversation.id, { peerName: name });
                if (currentUser?.email) {
                  setNickname(currentUser.email, activeConversation.peerId, name);
                  try {
                    await patchConversationMetadata(activeConversation.id, {
                      user: currentUser.email,
                      metadata_patch: {
                        nicknames: {
                          [currentUser.email.toLowerCase()]: {
                            [activeConversation.peerId.toLowerCase()]: name,
                          },
                        },
                      },
                    });
                  } catch {
                    // ignore sync failure
                  }
                }
              }}
              onClose={() => setInfoPanelOpen(false)}
            />
          </div>
        </>
      )}
    </div>
  );
}

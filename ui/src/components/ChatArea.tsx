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
import { dispatchPrivacyHideAll } from "@/hooks/usePrivacyReveal";
import { useSettingsStore } from "@/store/useSettingsStore";

interface ChatAreaProps {
  conversationId: string;
  onBack?: () => void;
}

const EMPTY_MESSAGES: ChatMessage[] = [];

export function ChatArea({ conversationId, onBack }: ChatAreaProps) {
  const [infoPanelOpen, setInfoPanelOpen] = useState(false);
  const [highlightedMessageId, setHighlightedMessageId] = useState<string | null>(null);
  const conversations = useChatStore((s) => s.conversations);
  const updateConversation = useChatStore((s) => s.updateConversation);
  const currentUser = useAuthStore((s) => s.currentUser);
  const prefs = useSettingsStore((s) => s.prefs);

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
    if (!prefs.privacyMode || !prefs.hideOnWindowBlur) return;
    const onWindowBlur = () => dispatchPrivacyHideAll();
    const onVisibility = () => {
      if (document.visibilityState !== "visible") dispatchPrivacyHideAll();
    };
    window.addEventListener("blur", onWindowBlur);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("blur", onWindowBlur);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [prefs.hideOnWindowBlur, prefs.privacyMode]);

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

  return (
    <div className="flex h-full min-w-0 gap-3 lg:gap-4">
      <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden rounded-[2rem] border border-white/10 bg-slate-950/45 backdrop-blur-xl">
        <ChatHeader
          conversation={activeConversation}
          onBack={onBack}
          infoPanelOpen={infoPanelOpen}
          onToggleInfoPanel={() => setInfoPanelOpen((v) => !v)}
        />

        <div className="mx-auto mt-4 max-w-md rounded-3xl border border-violet-400/20 bg-violet-500/10 px-5 py-3 text-center text-sm text-zinc-300 shadow-[0_0_40px_rgba(124,58,237,0.18)] backdrop-blur">
          Tin nhắn được mã hóa đầu cuối
        </div>

        <DynamicWatermark
          enabled={prefs.privacyMode && prefs.watermarkEnabled}
          userEmail={currentUser?.email || undefined}
          userId={currentUser?.id || undefined}
          conversationId={activeConversation.id}
          peerName={activeConversation.peerName}
        />

        <MessageList messages={messages} conversationId={conversationId} highlightedMessageId={highlightedMessageId} />

        <MessageComposer conversationId={conversationId} />
      </div>

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

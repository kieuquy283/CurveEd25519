import { ChatMessage } from "@/types/models";

type ExtendedChatMessage = ChatMessage & {
  cryptoEnvelope?: Record<string, unknown>;
  metadata?: {
    envelope?: Record<string, unknown>;
  };
};

function getEnvelope(message: ChatMessage): Record<string, unknown> | null {
  const msg = message as ExtendedChatMessage;
  return msg.envelope ?? msg.cryptoEnvelope ?? msg.metadata?.envelope ?? null;
}

export function buildEncryptedClipboardText(message: ChatMessage): string {
  const envelope = getEnvelope(message);
  if (!envelope) {
    return "[CurveEd25519 encrypted message - open in app to view]";
  }

  const payload = {
    app: "CurveEd25519",
    type: "encrypted-message-export",
    version: 1,
    created_at: new Date().toISOString(),
    message_id: message.id,
    sender: message.from,
    receiver: message.to,
    suite: "X25519 + ChaCha20-Poly1305 + Ed25519",
    envelope,
  };

  return [
    "-----BEGIN CURVEED25519 ENCRYPTED MESSAGE-----",
    JSON.stringify(payload, null, 2),
    "-----END CURVEED25519 ENCRYPTED MESSAGE-----",
  ].join("\n");
}

export async function copyEncryptedMessage(message: ChatMessage): Promise<void> {
  const text = buildEncryptedClipboardText(message);
  await navigator.clipboard.writeText(text);
}

export async function copyPlaintextMessage(message: ChatMessage): Promise<void> {
  await navigator.clipboard.writeText(message.text || "");
}

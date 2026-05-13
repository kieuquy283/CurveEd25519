import { getApiBaseUrl } from "@/config/env";

async function parseOrThrow(response: Response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${response.status}`);
  }
  return data;
}

export async function listConversations(user: string) {
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/conversations?user=${encodeURIComponent(user)}`);
    return parseOrThrow(response) as Promise<{ ok: boolean; conversations: Array<Record<string, unknown>> }>;
  } catch (error) {
    if (error instanceof TypeError) {
      return { ok: false, conversations: [] };
    }
    throw error;
  }
}

export async function listConversationMessages(conversationId: string, user: string, limit = 100) {
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/api/conversations/${encodeURIComponent(conversationId)}/messages?user=${encodeURIComponent(user)}&limit=${limit}`
    );
    return parseOrThrow(response) as Promise<{ ok: boolean; messages: Array<Record<string, unknown>> }>;
  } catch (error) {
    if (error instanceof TypeError) {
      return { ok: false, messages: [] };
    }
    throw error;
  }
}

export async function saveConversationMessage(
  conversationId: string,
  payload: {
    sender_email: string;
    receiver_email: string;
    packet_id?: string;
    message_type: string;
    ciphertext_envelope?: Record<string, unknown>;
    plaintext_preview?: string;
    attachment_json?: Record<string, unknown>;
    crypto_debug?: Record<string, unknown>;
    status?: string;
    connection_id?: string;
  }
) {
  const response = await fetch(`${getApiBaseUrl()}/api/conversations/${encodeURIComponent(conversationId)}/messages/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(response) as Promise<{ ok: boolean; conversation_id: string; message: Record<string, unknown> }>;
}

export async function patchConversationMetadata(
  conversationId: string,
  payload: {
    user: string;
    metadata_patch: Record<string, unknown>;
  }
) {
  const response = await fetch(`${getApiBaseUrl()}/api/conversations/${encodeURIComponent(conversationId)}/metadata`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(response) as Promise<{ ok: boolean; conversation_id: string; metadata: Record<string, unknown> }>;
}

export type AuditEventType =
  | "message_revealed"
  | "message_copied_encrypted"
  | "plaintext_copy_attempt_blocked"
  | "plaintext_copied_explicit"
  | "file_download_attempt"
  | "file_download_confirmed"
  | "privacy_mode_enabled"
  | "privacy_mode_disabled";

export interface AuditEventPayload {
  user_email?: string;
  conversation_id?: string;
  message_id?: string;
  peer_email?: string;
  event_type: AuditEventType;
  created_at?: string;
  metadata?: Record<string, unknown>;
}

export async function logAuditEvent(payload: AuditEventPayload): Promise<void> {
  const body = {
    ...payload,
    created_at: payload.created_at || new Date().toISOString(),
  };

  try {
    const { getApiBaseUrl } = await import("@/config/env");
    await fetch(`${getApiBaseUrl()}/api/audit/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    // best effort only
  }
}

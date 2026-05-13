import { getApiBaseUrl } from "@/config/env";

async function parseOrThrow(response: Response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data?.detail;
    if (typeof detail === "string") throw new Error(detail);
    if (typeof detail?.message === "string") throw new Error(detail.message);
    throw new Error(typeof data?.error === "string" ? data.error : `HTTP ${response.status}`);
  }
  return data;
}

export function normalizeEmail(value: string): string {
  return (value || "").trim().toLowerCase();
}

export function makeConnectionPairKey(userEmail: string, peerEmail: string): string {
  return [normalizeEmail(userEmail), normalizeEmail(peerEmail)].sort().join("::");
}

export type ConnectionStatusReason =
  | "verified_connection"
  | "missing_connection"
  | "pending_connection"
  | "peer_not_found"
  | "peer_not_verified"
  | "missing_crypto_profile";

export interface ConnectionStatusResponse {
  ok: boolean;
  user: { email?: string; display_name?: string; user_id?: string };
  peer: {
    email?: string;
    display_name?: string;
    user_id?: string;
    account_exists: boolean;
    verified: boolean;
    profile_exists: boolean;
    has_x25519_public_key: boolean;
    has_ed25519_public_key: boolean;
  };
  connection: {
    exists: boolean;
    id?: string | null;
    status: "pending" | "verified" | "none";
    requester_email?: string | null;
    recipient_email?: string | null;
    trusted: boolean;
    verified_at?: string | null;
  };
  can_send_encrypted: boolean;
  reason: ConnectionStatusReason;
}

export async function getConnectionStatus(user: string, peer: string): Promise<ConnectionStatusResponse> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/connections/status?user=${encodeURIComponent(user)}&peer=${encodeURIComponent(peer)}`
  );
  return parseOrThrow(response);
}

export async function requestConnection(params: { from_user: string; to: string }) {
  const response = await fetch(`${getApiBaseUrl()}/api/connections/request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return parseOrThrow(response);
}

export async function verifyConnection(params: { connection_id: string; user: string; code: string }) {
  const response = await fetch(`${getApiBaseUrl()}/api/connections/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return parseOrThrow(response);
}

export async function listTrustedContacts(user: string): Promise<{
  ok: boolean;
  contacts: Array<{
    connection_id: string;
    user_id: string;
    email: string;
    display_name: string;
    x25519_public_key: string;
    ed25519_public_key: string;
    key_fingerprint: string;
    verified_at: string;
    trusted: boolean;
    key_changed?: boolean;
  }>;
}> {
  const response = await fetch(`${getApiBaseUrl()}/api/connections/contacts?user=${encodeURIComponent(user)}`);
  return parseOrThrow(response);
}

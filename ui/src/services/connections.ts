import { getApiBaseUrl } from "@/config/env";

async function parseOrThrow(response: Response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${response.status}`);
  }
  return data;
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

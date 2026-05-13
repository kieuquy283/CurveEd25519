import { buildApiBaseCandidates, getApiBaseUrl } from "@/config/env";

export const getConversationApiBaseUrl = () => getApiBaseUrl();

export interface DecryptIncomingResult {
  plaintext: string;
  debug?: Record<string, unknown>;
}

export interface EncryptConversationResult {
  ok: boolean;
  envelope: Record<string, unknown>;
  debug?: Record<string, unknown>;
}

export interface SignFileResult {
  ok: boolean;
  signed_file: import("@/types/models").SignedFileContainer;
  debug: import("@/types/models").SignatureDebug;
}

export interface VerifyFileResult {
  ok: boolean;
  valid: boolean;
  message: string;
  file?: {
    filename: string;
    mime_type: string;
    content_b64: string;
    size: number;
  };
  debug: {
    algorithm: string;
    hash: string;
    signer: string;
  };
}

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs = 15000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") return data.detail;
    if (typeof data?.detail?.message === "string") return data.detail.message;
    if (typeof data?.detail?.error === "string") return data.detail.error;
    if (typeof data?.error === "string") return data.error;
    if (typeof data?.message === "string") return data.message;
  } catch {
    // ignore
  }
  try {
    return await response.text();
  } catch {
    return "";
  }
}

export async function encryptConversationMessage(params: {
  sender: string;
  recipient: string;
  plaintext: string;
}): Promise<EncryptConversationResult> {
  const apiBaseUrl = getConversationApiBaseUrl();
  const baseCandidates = buildApiBaseCandidates(apiBaseUrl);

  let lastNetworkError: unknown;

  for (const base of baseCandidates) {
    let response: Response;

    try {
      response = await fetchWithTimeout(
        `${base}/api/conversation/encrypt`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(params),
        },
        15000
      );
    } catch (error) {
      lastNetworkError = error;
      continue;
    }

    if (!response.ok) {
      const errorText = await readErrorMessage(response);
      throw new Error(
        `Encrypt API failed (${response.status}) at ${base}: ${errorText || "unknown error"}`
      );
    }

    return response.json();
  }

  throw new Error(
    `Không kết nối được backend crypto API. Vui lòng thử lại.${lastNetworkError instanceof Error ? ` Cause: ${lastNetworkError.message}` : ""}`.trim()
  );
}

export async function decryptIncomingMessage(params: {
  receiver: string;
  sender: string;
  envelope: unknown;
}): Promise<DecryptIncomingResult> {
  const response = await fetchWithTimeout(
    `${getConversationApiBaseUrl()}/api/conversation/decrypt`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        receiver: params.receiver,
        sender: params.sender,
        envelope: params.envelope,
      }),
    },
    15000
  );

  if (!response.ok) {
    const detail = await readErrorMessage(response);
    throw new Error(detail || "Failed to decrypt incoming message");
  }

  const data = await response.json();

  if (!data.ok) {
    throw new Error("Invalid decrypt response");
  }

  if (typeof data.plaintext === "string") {
    return {
      plaintext: data.plaintext,
      debug: data.debug,
    };
  }

  if (data.message?.type === "file") {
    const attachment = {
      id: crypto.randomUUID(),
      fileName: data.message.filename ?? "attachment",
      mimeType: data.message.mime_type ?? "application/octet-stream",
      size: data.message.size ?? 0,
      content_b64: data.message.content_b64,
      dataBase64: data.message.content_b64,
      crypto: {
        encrypted: true,
        decrypted: true,
        encryption: "ChaCha20-Poly1305",
        keyExchange: "X25519",
        kdf: "HKDF-SHA256",
        signature: "Ed25519",
      },
    };

    return {
      plaintext: JSON.stringify({
        type: "file",
        text: `📎 ${attachment.fileName}`,
        attachment,
      }),
      debug: data.debug,
    };
  }

  throw new Error("Invalid decrypt response");
}

export async function signFileContainer(params: {
  signer: string;
  filename: string;
  mime_type: string;
  content_b64: string;
}): Promise<SignFileResult> {
  const apiBaseUrl = getConversationApiBaseUrl();
  const response = await fetchWithTimeout(
    `${apiBaseUrl}/api/signature/sign-file`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    },
    15000
  );

  if (!response.ok) {
    const errorText = await readErrorMessage(response);
    throw new Error(`Sign-file failed (${response.status}): ${errorText}`);
  }

  return response.json();
}

export async function verifySignedFileContainer(params: {
  signed_file: import("@/types/models").SignedFileContainer;
  verifier?: string;
}): Promise<VerifyFileResult> {
  const apiBaseUrl = getConversationApiBaseUrl();
  const response = await fetchWithTimeout(
    `${apiBaseUrl}/api/signature/verify-file`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    },
    15000
  );

  if (!response.ok) {
    const errorText = await readErrorMessage(response);
    throw new Error(`Verify-file failed (${response.status}): ${errorText}`);
  }

  return response.json();
}

import { Attachment, SignedFileContainer } from "@/types/models";

type AnyRecord = Record<string, unknown>;

function asRecord(value: unknown): AnyRecord | null {
  return value && typeof value === "object" ? (value as AnyRecord) : null;
}

function decodeDataUrl(url: string): string | null {
  const marker = ";base64,";
  const idx = url.indexOf(marker);
  if (idx < 0) return null;
  return url.slice(idx + marker.length);
}

function b64ToUtf8(b64: string): string | null {
  try {
    if (typeof window !== "undefined" && typeof atob === "function") {
      const binary = atob(b64);
      const bytes = Uint8Array.from(binary, (ch) => ch.charCodeAt(0));
      return new TextDecoder().decode(bytes);
    }
    return Buffer.from(b64, "base64").toString("utf-8");
  } catch {
    return null;
  }
}

function parseSignedContainer(value: unknown): SignedFileContainer | null {
  const record = asRecord(value);
  if (!record) return null;
  if (String(record.type || "") !== "signed-file") return null;
  const filename = String(record.filename || "");
  const mimeType = String(record.mimeType || record.mime_type || "");
  const content_b64 = String(record.content_b64 || record.dataBase64 || "");
  if (!filename || !mimeType || !content_b64) return null;
  return {
    version: Number(record.version || 1),
    type: "signed-file",
    filename,
    mimeType,
    size: Number(record.size || 0),
    content_b64,
    signer: String(record.signer || ""),
    signer_public_key: String(record.signer_public_key || ""),
    algorithm: "Ed25519",
    hash: "SHA-256",
    signed_at: String(record.signed_at || ""),
    signature: String(record.signature || ""),
  };
}

function extractSignedContainerFromBase64(raw: AnyRecord): SignedFileContainer | null {
  const b64 =
    (typeof raw.content_b64 === "string" && raw.content_b64) ||
    (typeof raw.dataBase64 === "string" && raw.dataBase64) ||
    (typeof raw.url === "string" && raw.url.startsWith("data:") ? decodeDataUrl(raw.url) : "") ||
    "";
  if (!b64) return null;
  const text = b64ToUtf8(b64);
  if (!text) return null;
  try {
    return parseSignedContainer(JSON.parse(text));
  } catch {
    return null;
  }
}

export function detectSignedFile(raw: unknown): boolean {
  const record = asRecord(raw);
  if (!record) return false;
  const fileName = String(record.fileName || record.filename || "").toLowerCase();
  const kind = String(record.kind || record.type || "").toLowerCase();
  if (kind === "signed-file") return true;
  if (fileName.endsWith(".signed.json") || fileName.includes(".signed")) return true;
  if (asRecord(record.signed_file) || asRecord(record.signed_file_json)) return true;
  return Boolean(extractSignedContainerFromBase64(record));
}

export function normalizeChatAttachment(raw: unknown): Attachment | null {
  const record = asRecord(raw);
  if (!record) return null;

  const id = String(record.id || crypto.randomUUID());
  const fileName = String(record.fileName || record.filename || "attachment");
  const mimeType = String(record.mimeType || record.mime_type || "application/octet-stream");
  const size = Number(record.size || 0);
  const content_b64 =
    typeof record.content_b64 === "string"
      ? record.content_b64
      : typeof record.dataBase64 === "string"
        ? record.dataBase64
        : undefined;
  const url =
    typeof record.url === "string"
      ? record.url
      : content_b64
        ? `data:${mimeType};base64,${content_b64}`
        : undefined;

  const signed_file_json =
    asRecord(record.signed_file_json) ||
    asRecord(record.signed_file) ||
    extractSignedContainerFromBase64(record);
  const signed = detectSignedFile(record);
  const metadata: AnyRecord = {
    ...(asRecord(record.metadata) || {}),
  };
  if (signed) {
    metadata.type = "signed-file";
  }
  if (signed_file_json) {
    metadata.signed_file_json = signed_file_json;
    metadata.signature = {
      signer: String((signed_file_json as AnyRecord).signer || ""),
      signed_at: String((signed_file_json as AnyRecord).signed_at || ""),
      algorithm: String((signed_file_json as AnyRecord).algorithm || "Ed25519"),
      hash: String((signed_file_json as AnyRecord).hash || "SHA-256"),
    };
    metadata.original_file = {
      filename: String((signed_file_json as AnyRecord).filename || fileName),
      mime_type: String((signed_file_json as AnyRecord).mimeType || mimeType),
      size: Number((signed_file_json as AnyRecord).size || size),
      content_b64: String((signed_file_json as AnyRecord).content_b64 || content_b64 || ""),
    };
  }

  return {
    id,
    fileName,
    mimeType,
    size,
    content_b64,
    dataBase64: content_b64,
    url,
    uploaded: true,
    crypto:
      asRecord(record.crypto) as Attachment["crypto"] ||
      {
        encrypted: true,
        decrypted: true,
        encryption: "ChaCha20-Poly1305",
        keyExchange: "X25519",
        kdf: "HKDF-SHA256",
        signature: "Ed25519",
      },
    metadata,
  };
}


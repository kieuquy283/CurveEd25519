import { SignedFileContainer, VerificationResult } from "@/types/models";
import { verifySignedFile } from "@/services/signature";

type AttachmentLike = {
  fileName?: string;
  mimeType?: string;
  url?: string;
  dataBase64?: string;
  content_b64?: string;
};

function decodeDataUrl(url: string): string | null {
  const marker = ";base64,";
  const idx = url.indexOf(marker);
  if (idx === -1) return null;
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

function normalizeSignedFile(obj: Record<string, unknown>): SignedFileContainer | null {
  if ((obj.type as string) !== "signed-file") return null;
  const filename = (obj.filename ?? obj.fileName) as string | undefined;
  const mimeType = (obj.mimeType ?? obj.mime_type) as string | undefined;
  const content_b64 = (obj.content_b64 ?? obj.dataBase64) as string | undefined;
  if (!filename || !mimeType || !content_b64) return null;
  return {
    version: Number(obj.version ?? 1),
    type: "signed-file",
    filename,
    mimeType,
    size: Number(obj.size ?? 0),
    content_b64,
    signer: String(obj.signer ?? ""),
    signer_public_key: String(obj.signer_public_key ?? ""),
    algorithm: "Ed25519",
    hash: "SHA-256",
    signed_at: String(obj.signed_at ?? ""),
    signature: String(obj.signature ?? ""),
  };
}

export function detectSignedFileContainer(attachment: AttachmentLike): SignedFileContainer | null {
  const fileName = (attachment.fileName || "").toLowerCase();
  const mimeType = (attachment.mimeType || "").toLowerCase();
  const looksLikeSignedContainer =
    fileName.endsWith(".signed.json") || mimeType.includes("application/json");

  const fromDirect = attachment.content_b64 || attachment.dataBase64 || "";
  let payloadBase64 = fromDirect.trim();
  if (!payloadBase64 && attachment.url?.startsWith("data:")) {
    payloadBase64 = decodeDataUrl(attachment.url) ?? "";
  }
  if (!payloadBase64 || !looksLikeSignedContainer) return null;
  const text = b64ToUtf8(payloadBase64);
  if (!text) return null;
  try {
    const parsed = JSON.parse(text) as Record<string, unknown>;
    return normalizeSignedFile(parsed);
  } catch {
    return null;
  }
}

export function detectSignedFileContainerFromAttachment(attachment: AttachmentLike): SignedFileContainer | null {
  return detectSignedFileContainer(attachment);
}

export async function verifySignedContainer(
  signedFile: SignedFileContainer,
  verifier?: string,
  expectedSigner?: string
): Promise<VerificationResult> {
  return verifySignedFile({
    signed_file: signedFile,
    verifier,
    expected_signer: expectedSigner,
  });
}

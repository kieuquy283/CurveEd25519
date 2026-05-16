const ENCRYPTED_EXPORT_PREFIX = "-----BEGIN CURVEED25519 ENCRYPTED MESSAGE-----";

export function looksLikeEncryptedExport(value: string | undefined | null): boolean {
  if (!value) return false;
  return value.trimStart().startsWith(ENCRYPTED_EXPORT_PREFIX);
}

export function sanitizeVisibleMessageText(
  value: string | undefined | null,
  fallback?: string | null
): string {
  if (looksLikeEncryptedExport(value)) {
    const safeFallback = (fallback || "").trim();
    return safeFallback || "[Tin nhắn mã hóa]";
  }
  return value || "";
}

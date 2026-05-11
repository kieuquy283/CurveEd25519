/**
 * Trust helpers — fingerprint formatting, safety number generation, clipboard helpers.
 */
import { TrustEntry } from "@/store/useTrustStore";

export function formatFingerprint(fp?: string): string {
  if (!fp) return "";
  // Group into 4-char blocks for readability
  return fp.replace(/(.{4})/g, "$1 ").trim();
}

export function generateSafetyNumber(a?: string, b?: string): string {
  // Simple deterministic safety number: hash both fingerprints and take numeric groups
  const s = `${a ?? ""}:${b ?? ""}`;
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    hash = (hash * 31 + s.charCodeAt(i)) >>> 0;
  }
  const parts: string[] = [];
  for (let i = 0; i < 4; i++) {
    parts.push(((hash >> (i * 8)) & 0xff).toString().padStart(3, "0"));
  }
  return parts.join("-");
}

export async function copyToClipboard(text: string): Promise<void> {
  if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(text);
  } else if (typeof window !== "undefined") {
    const el = document.createElement("textarea");
    el.value = text;
    document.body.appendChild(el);
    el.select();
    document.execCommand("copy");
    document.body.removeChild(el);
  }
}

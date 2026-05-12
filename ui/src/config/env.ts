const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_WS_URL = "ws://127.0.0.1:8765";

function isProductionBuild(): boolean {
  return process.env.NODE_ENV === "production";
}

function ensureApiProtocol(url: string): string {
  const trimmed = url.trim().replace(/\/+$/, "");
  if (!trimmed) return DEFAULT_API_BASE_URL;
  if (trimmed.startsWith("//")) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL must include protocol (https:// or http://).");
  }
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  return isProductionBuild() ? `https://${trimmed}` : `http://${trimmed}`;
}

function ensureWsProtocol(url: string): string {
  const trimmed = url.trim();
  if (!trimmed) return DEFAULT_WS_URL;
  if (trimmed.startsWith("//")) {
    throw new Error("NEXT_PUBLIC_WS_URL must include protocol (wss:// or ws://).");
  }
  if (/^wss?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  return isProductionBuild() ? `wss://${trimmed}` : `ws://${trimmed}`;
}

export function getApiBaseUrl(): string {
  return ensureApiProtocol(process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL);
}

export function getWsUrl(): string {
  return ensureWsProtocol(process.env.NEXT_PUBLIC_WS_URL || DEFAULT_WS_URL);
}

export function buildApiBaseCandidates(primary?: string): string[] {
  const normalized = ensureApiProtocol(primary || getApiBaseUrl());
  const candidates = [normalized];
  if (normalized === "http://127.0.0.1:8000") {
    candidates.push("http://localhost:8000");
  } else if (normalized === "http://localhost:8000") {
    candidates.push("http://127.0.0.1:8000");
  }
  return [...new Set(candidates)];
}

export function getApiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").trim();
}

export function getWsUrl(): string {
  return (process.env.NEXT_PUBLIC_WS_URL || "ws://127.0.0.1:8765").trim();
}

export function buildApiBaseCandidates(primary?: string): string[] {
  const normalized = (primary || getApiBaseUrl()).replace(/\/+$/, "");
  const candidates = [normalized];

  if (normalized === "http://127.0.0.1:8000") {
    candidates.push("http://localhost:8000");
  } else if (normalized === "http://localhost:8000") {
    candidates.push("http://127.0.0.1:8000");
  }

  if (typeof window !== "undefined" && window.location?.hostname) {
    candidates.push(`http://${window.location.hostname}:8000`);
  }

  return [...new Set(candidates)];
}

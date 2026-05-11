/**
 * Presence helpers — normalize presence payloads from backend.
 */

import { PresencePayload } from "@/types/packets";

export function isOnlineFromPayload(payload: Partial<PresencePayload> | undefined): boolean {
  if (!payload) return false;
  return payload.status === "online";
}

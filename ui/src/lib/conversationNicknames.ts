const STORAGE_KEY = "conversation_nicknames_v1";

type NicknameMap = Record<string, string>;

function toKey(owner: string, peer: string) {
  return `${owner.trim().toLowerCase()}::${peer.trim().toLowerCase()}`;
}

function readAll(): NicknameMap {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as NicknameMap;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeAll(map: NicknameMap) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
}

export function getNickname(owner: string, peer: string): string | null {
  const map = readAll();
  return map[toKey(owner, peer)] || null;
}

export function setNickname(owner: string, peer: string, nickname: string) {
  const map = readAll();
  map[toKey(owner, peer)] = nickname;
  writeAll(map);
}


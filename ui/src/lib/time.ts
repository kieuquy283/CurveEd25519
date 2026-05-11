export function formatTime(timestamp: string | number | Date): string {
  const date = new Date(timestamp);

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRelativeTime(
  timestamp: string | number | Date
): string {
  const now = Date.now();
  const target = new Date(timestamp).getTime();

  const diff = Math.floor((now - target) / 1000);

  if (diff < 60) return "now";

  if (diff < 3600) {
    return `${Math.floor(diff / 60)}m`;
  }

  if (diff < 86400) {
    return `${Math.floor(diff / 3600)}h`;
  }

  return `${Math.floor(diff / 86400)}d`;
}
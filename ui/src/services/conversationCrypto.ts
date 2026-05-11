const API_BASE_URL = "http://localhost:8000";

export async function decryptIncomingMessage(params: {
  receiver: string;
  sender: string;
  envelope: unknown;
}) {
  const response = await fetch(`${API_BASE_URL}/api/conversation/decrypt`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      receiver: params.receiver,
      sender: params.sender,
      envelope: params.envelope,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to decrypt incoming message");
  }

  const data = await response.json();

  if (!data.ok || typeof data.plaintext !== "string") {
    throw new Error("Invalid decrypt response");
  }

  return data.plaintext;
}
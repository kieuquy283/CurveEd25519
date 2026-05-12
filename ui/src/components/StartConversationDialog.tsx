import { useMemo, useState } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  trustedContacts: Array<{
    id: string;
    name: string;
    peerId: string;
    fingerprint?: string;
    trusted?: boolean;
  }>;
  onCreate: (contact: { id: string; name: string }) => void;
  connectTo: string;
  setConnectTo: (value: string) => void;
  connectionId: string;
  setConnectionId: (value: string) => void;
  verifyCode: string;
  setVerifyCode: (value: string) => void;
  connectionMsg: string;
  devCode: string;
  onSendRequest: () => Promise<void>;
  onVerifyConnection: () => Promise<boolean>;
};

export default function StartConversationDialog({
  open,
  onClose,
  trustedContacts,
  onCreate,
  connectTo,
  setConnectTo,
  connectionId,
  setConnectionId,
  verifyCode,
  setVerifyCode,
  connectionMsg,
  devCode,
  onSendRequest,
  onVerifyConnection,
}: Props) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [search, setSearch] = useState("");
  const matchedTrusted = useMemo(
    () =>
      trustedContacts.find(
        (contact) =>
          contact.peerId.toLowerCase() === connectTo.trim().toLowerCase() ||
          contact.id.toLowerCase() === connectTo.trim().toLowerCase()
      ),
    [trustedContacts, connectTo]
  );
  const filtered = trustedContacts.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-40">
      <div className="bg-zinc-900 w-[520px] max-w-[95vw] rounded-xl p-4 border border-zinc-700">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Connect With Another User</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-zinc-600 px-2 py-1 text-xs hover:border-zinc-400"
          >
            X
          </button>
        </div>

        <div className="rounded-lg border border-zinc-700 p-3 mb-4">
          <div className="mb-2 text-xs text-zinc-300">Request connection</div>
          <input
            type="text"
            placeholder="Email or user_id"
            value={connectTo}
            onChange={(e) => setConnectTo(e.target.value)}
            className="mb-2 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm"
          />
          <button
            type="button"
            disabled={isSubmitting}
            onClick={async () => {
              setIsSubmitting(true);
              try {
                await onSendRequest();
              } finally {
                setIsSubmitting(false);
              }
            }}
            className="w-full rounded border border-zinc-600 px-2 py-1 text-sm hover:border-zinc-400 disabled:opacity-50"
          >
            Send connection request
          </button>

          <div className="mt-3 mb-2 text-xs text-zinc-300">Verify connection</div>
          <input
            type="text"
            placeholder="Connection ID"
            value={connectionId}
            onChange={(e) => setConnectionId(e.target.value)}
            className="mb-2 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm"
          />
          <input
            type="text"
            placeholder="Email verification code"
            value={verifyCode}
            onChange={(e) => setVerifyCode(e.target.value)}
            className="mb-2 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm"
          />
          <button
            type="button"
            disabled={isSubmitting}
            onClick={async () => {
              setIsSubmitting(true);
              try {
                const ok = await onVerifyConnection();
                if (ok) {
                  onClose();
                }
              } finally {
                setIsSubmitting(false);
              }
            }}
            className="w-full rounded border border-zinc-600 px-2 py-1 text-sm hover:border-zinc-400 disabled:opacity-50"
          >
            Verify connection
          </button>
          {connectionMsg ? <div className="mt-2 text-xs text-zinc-300">{connectionMsg}</div> : null}
          {devCode ? <div className="mt-1 text-xs text-amber-300">dev_code: {devCode}</div> : null}
          {matchedTrusted ? (
            <div className="mt-2 rounded border border-emerald-500/40 bg-emerald-500/10 p-2 text-xs text-emerald-200">
              <div>Trusted: {matchedTrusted.name}</div>
              <div>Peer ID: {matchedTrusted.peerId}</div>
              <div>Fingerprint: {matchedTrusted.fingerprint || "-"}</div>
            </div>
          ) : null}
        </div>

        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search trusted contacts..."
          className="w-full p-2 rounded bg-zinc-800 mb-4"
        />

        <div className="space-y-2 max-h-[300px] overflow-y-auto">
          {filtered.map((contact) => (
            <button
              key={contact.id}
              onClick={() => {
                onCreate(contact);
                onClose();
              }}
              className="w-full text-left p-3 rounded bg-zinc-800 hover:bg-zinc-700"
            >
              <div>{contact.name}</div>
              <div className="text-xs text-zinc-400">{contact.peerId}</div>
            </button>
          ))}
        </div>
        <div className="mt-3 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-zinc-600 px-3 py-1 text-sm hover:border-zinc-400"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

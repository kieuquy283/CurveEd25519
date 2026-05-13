import { useMemo, useState } from "react";
import GlobalModal from "@/components/ui/GlobalModal";

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
    <GlobalModal
      open={open}
      onClose={onClose}
      title="Connect With Another User"
      size="lg"
    >
      <div className="w-full rounded-[2rem]">
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-5">
          <h2 className="text-lg font-semibold">Connect With Another User</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs hover:bg-white/[0.08]"
          >
            X
          </button>
        </div>

        <div className="space-y-4 p-6">
        <div className="mb-3 flex items-center justify-between">
          <div className="text-xs text-zinc-400">Manage trusted contacts and connection verification.</div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3 mb-4">
          <div className="mb-2 text-xs text-zinc-300">Request connection</div>
          <input
            type="text"
            placeholder="Email or user_id"
            value={connectTo}
            onChange={(e) => setConnectTo(e.target.value)}
            className="mb-2 w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm"
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
            className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm hover:bg-white/[0.08] disabled:opacity-50"
          >
            Send connection request
          </button>

          <div className="mt-3 mb-2 text-xs text-zinc-300">Verify connection</div>
          <input
            type="text"
            placeholder="Connection ID"
            value={connectionId}
            onChange={(e) => setConnectionId(e.target.value)}
            className="mb-2 w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm"
          />
          <input
            type="text"
            placeholder="Email verification code"
            value={verifyCode}
            onChange={(e) => setVerifyCode(e.target.value)}
            className="mb-2 w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm"
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
            className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm hover:bg-white/[0.08] disabled:opacity-50"
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
          className="mb-4 w-full rounded-xl border border-white/10 bg-white/[0.04] p-2.5"
        />

        <div className="space-y-2 max-h-[300px] overflow-y-auto">
          {filtered.map((contact) => (
            <button
              key={contact.id}
              onClick={() => {
                onCreate(contact);
                onClose();
              }}
              className="w-full rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-left hover:bg-white/[0.08]"
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
            className="rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-1.5 text-sm hover:bg-white/[0.08]"
          >
            Cancel
          </button>
        </div>
      </div>
      </div>
    </GlobalModal>
  );
}

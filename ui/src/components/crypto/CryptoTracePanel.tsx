"use client";

import React, { useMemo } from "react";
import {
  CheckCircle2,
  FileText,
  Fingerprint,
  KeyRound,
  LockKeyhole,
  ShieldCheck,
  X,
} from "lucide-react";

type CryptoTracePanelProps = {
  envelope?: Record<string, unknown>;
  debug?: Record<string, unknown>;
  mode?: "encrypt" | "decrypt";
  onClose?: () => void;
};

function preview(value: unknown, length = 96) {
  if (value === undefined || value === null || value === "") return "-";

  const text =
    typeof value === "string"
      ? value
      : JSON.stringify(value, null, 2);

  if (text.length <= length) return text;

  return `${text.slice(0, length)}…`;
}

function sizeOfBase64(value?: string) {
  if (!value) return "-";

  try {
    const padding = value.endsWith("==") ? 2 : value.endsWith("=") ? 1 : 0;
    const bytes = Math.floor((value.length * 3) / 4) - padding;
    return `${bytes.toLocaleString()} bytes`;
  } catch {
    return "-";
  }
}

function sanitizeDebug(debug: Record<string, unknown> | undefined) {
  if (!debug) return {};

  const blocked = [
    "private_key",
    "privateKey",
    "shared_secret",
    "sharedSecret",
    "message_key",
    "messageKey",
    "root_key",
    "rootKey",
    "chain_key",
    "chainKey",
    "ephemeral_private_key_b64",
  ];

  const clone = JSON.parse(JSON.stringify(debug));

  function walk(obj: unknown) {
    if (!obj || typeof obj !== "object") return;

    const record = obj as Record<string, unknown>;
    for (const key of Object.keys(record)) {
      if (blocked.includes(key)) {
        record[key] = "[hidden]";
      } else {
        walk(record[key]);
      }
    }
  }

  walk(clone);

  return clone;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
}

function Row({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: unknown;
  mono?: boolean;
}) {
  return (
    <div className="space-y-1">
      <div className="text-[11px] uppercase tracking-wide text-zinc-500">
        {label}
      </div>
      <div
        className={[
          "text-sm text-zinc-200 break-all",
          mono ? "font-mono text-xs" : "",
        ].join(" ")}
      >
        {preview(value)}
      </div>
    </div>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-4 space-y-3">
      <div className="flex items-center gap-2">
        <div className="text-blue-400">{icon}</div>
        <h4 className="font-semibold text-zinc-100">{title}</h4>
      </div>
      {children}
    </section>
  );
}

export default function CryptoTracePanel({
  envelope,
  debug,
  mode = "encrypt",
  onClose,
}: CryptoTracePanelProps) {
  const safeDebug = useMemo(() => sanitizeDebug(debug), [debug]);

  const header = asRecord(envelope?.header);
  const crypto = asRecord(header.crypto);
  const sender = asRecord(header.sender);
  const receiver = asRecord(header.receiver);
  const signature = asRecord(envelope?.signature);

  const messageId =
    header?.message_id ??
    safeDebug?.message_id ??
    "-";

  const createdAt =
    header?.created_at ??
    safeDebug?.created_at ??
    "-";

  const suite =
    header?.suite ??
    safeDebug?.suite ??
    "X25519+HKDF-SHA256+ChaCha20-Poly1305+Ed25519";

  const ciphertext =
    envelope?.ciphertext ??
    safeDebug?.ciphertext_b64 ??
    "-";

  const wrappedKey =
    envelope?.wrapped_key ??
    safeDebug?.wrapped_key_b64 ??
    "-";

  const verified =
    safeDebug?.verified ??
    safeDebug?.signature_verified ??
    (mode === "encrypt" ? "signed" : "unknown");

  const payloadSize =
    safeDebug?.plaintext_size ??
    safeDebug?.payload_size ??
    sizeOfBase64(ciphertext);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
        aria-label="Close crypto trace"
      />

      <div className="relative z-10 w-full max-w-4xl max-h-[86vh] overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900 text-zinc-100 shadow-2xl">
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <div>
            <h3 className="text-lg font-semibold">
              {mode === "encrypt" ? "Encryption Trace" : "Decryption Trace"}
            </h3>
            <p className="text-xs text-zinc-400">
              Visualized Curve25519 secure message envelope
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
          >
            <X size={18} />
          </button>
        </div>

        <div className="max-h-[calc(86vh-72px)] overflow-y-auto p-5 space-y-4">
          <Section icon={<FileText size={18} />} title="Message Envelope">
            <div className="grid gap-3 md:grid-cols-2">
              <Row label="Message ID" value={messageId} mono />
              <Row label="Created At" value={createdAt} />
              <Row label="Mode" value={mode} />
              <Row label="Suite" value={suite} />
              <Row label="Payload Size" value={payloadSize} />
              <Row label="Ciphertext Size" value={sizeOfBase64(ciphertext)} />
            </div>
          </Section>

          <Section icon={<Fingerprint size={18} />} title="Identity Binding">
            <div className="grid gap-3 md:grid-cols-2">
              <Row
                label="Sender Name"
                value={sender?.name ?? sender?.username ?? safeDebug?.sender}
              />
              <Row
                label="Receiver Name"
                value={receiver?.name ?? receiver?.username ?? safeDebug?.receiver}
              />
              <Row
                label="Sender Ed25519 Public Key"
                value={sender?.ed25519_public_key}
                mono
              />
              <Row
                label="Sender Ed25519 Fingerprint"
                value={
                  sender?.ed25519_fingerprint ??
                  safeDebug?.sender_sig_fingerprint
                }
                mono
              />
              <Row
                label="Recipient X25519 Fingerprint"
                value={
                  receiver?.x25519_fingerprint ??
                  safeDebug?.recipient_x25519_fingerprint
                }
                mono
              />
            </div>
          </Section>

          <Section icon={<KeyRound size={18} />} title="1. X25519 Key Agreement">
            <div className="grid gap-3 md:grid-cols-2">
              <Row
                label="Ephemeral Public Key"
                value={
                  crypto?.ephemeral_x25519_public_key ??
                  safeDebug?.ephemeral_public_key_b64
                }
                mono
              />
              <Row
                label="Ephemeral Fingerprint"
                value={
                  crypto?.ephemeral_x25519_fingerprint ??
                  safeDebug?.ephemeral_x25519_fingerprint
                }
                mono
              />
              <Row
                label="Shared Secret"
                value="[hidden]"
                mono
              />
              <Row
                label="Security Note"
                value="Only public metadata is shown. Shared secrets and private keys are never displayed."
              />
            </div>
          </Section>

          <Section icon={<LockKeyhole size={18} />} title="2. HKDF-SHA256 Key Derivation">
            <div className="grid gap-3 md:grid-cols-2">
              <Row
                label="Salt Wrap"
                value={crypto?.salt_wrap ?? safeDebug?.salt_wrap_b64}
                mono
              />
              <Row
                label="Derived Key Material"
                value="[hidden]"
                mono
              />
              <Row
                label="Wrapped Payload Key"
                value={wrappedKey}
                mono
              />
            </div>
          </Section>

          <Section icon={<ShieldCheck size={18} />} title="3. ChaCha20-Poly1305 AEAD">
            <div className="space-y-3">
              <div className="grid gap-3 md:grid-cols-2">
                <Row
                  label="Payload Nonce"
                  value={crypto?.payload_nonce ?? safeDebug?.payload_nonce_b64}
                  mono
                />
                <Row
                  label="AEAD Status"
                  value={
                    mode === "encrypt"
                      ? "Payload encrypted and authenticated"
                      : "Payload decrypted after authentication"
                  }
                />
              </div>

              <div>
                <div className="text-[11px] uppercase tracking-wide text-zinc-500 mb-1">
                  Ciphertext Preview
                </div>
                <pre className="max-h-32 overflow-auto rounded-lg bg-zinc-800 p-3 text-xs text-zinc-200 whitespace-pre-wrap break-all">
                  {preview(ciphertext, 700)}
                </pre>
              </div>
            </div>
          </Section>

          <Section icon={<CheckCircle2 size={18} />} title="4. Ed25519 Signature">
            <div className="grid gap-3 md:grid-cols-2">
              <Row
                label="Algorithm"
                value={signature?.algorithm ?? "Ed25519"}
              />
              <Row
                label="Verification Status"
                value={String(verified)}
              />
              <Row
                label="Signature Preview"
                value={signature?.value}
                mono
              />
              <Row
                label="Signed Data"
                value="Canonical header + wrapped key + ciphertext"
              />
            </div>
          </Section>

          {safeDebug && Object.keys(safeDebug).length > 0 && (
            <Section icon={<FileText size={18} />} title="Sanitized Debug Metadata">
              <pre className="max-h-60 overflow-auto rounded-lg bg-zinc-800 p-3 text-xs text-zinc-300 whitespace-pre-wrap">
                {JSON.stringify(safeDebug, null, 2)}
              </pre>
            </Section>
          )}
        </div>
      </div>
    </div>
  );
}

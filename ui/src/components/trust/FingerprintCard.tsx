"use client";
import React from "react";
import { formatFingerprint } from "@/services/trust";
import { useTrustStore } from "@/store/useTrustStore";

export default function FingerprintCard({ peerId }: { peerId: string }) {
  const entry = useTrustStore((s) => s.getEntry(peerId));
  const fp = entry?.fingerprint ?? "";

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-md p-3">
      <div className="text-sm text-slate-400">Fingerprint</div>
      <div className="mt-2 font-mono text-xs text-slate-200 break-words">{formatFingerprint(fp)}</div>
    </div>
  );
}

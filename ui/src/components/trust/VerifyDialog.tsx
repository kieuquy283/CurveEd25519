"use client";
import React from "react";
import { useTrustStore } from "@/store/useTrustStore";
import FingerprintCard from "./FingerprintCard";
import SafetyNumber from "./SafetyNumber";
import { copyToClipboard } from "@/services/trust";
import GlobalModal from "@/components/ui/GlobalModal";

export default function VerifyDialog({ peerId, onClose }: { peerId: string; onClose: () => void }) {
  const entry = useTrustStore((s) => s.getEntry(peerId));
  const updateTrust = useTrustStore((s) => s.updateTrustLevel);

  const fp = entry?.fingerprint ?? "";

  return (
    <GlobalModal open onClose={onClose} title="Verify Identity" size="lg">
      <div className="w-full p-6">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Verify Identity</h3>
          <button onClick={onClose} className="text-slate-400">Close</button>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4">
          <FingerprintCard peerId={peerId} />
          <SafetyNumber a={fp} b={fp} />
          <div className="flex gap-2 justify-end">
            <button onClick={() => copyToClipboard(fp)} className="px-3 py-2 rounded-md">Copy Fingerprint</button>
            <button onClick={() => updateTrust(peerId, "trusted")} className="px-3 py-2 bg-green-600 rounded-md">Mark Trusted</button>
            <button onClick={() => updateTrust(peerId, "untrusted")} className="px-3 py-2 bg-rose-600 rounded-md">Mark Untrusted</button>
          </div>
        </div>
      </div>
    </GlobalModal>
  );
}

"use client";

import React from "react";
import { CheckCheck, FileCheck2, ShieldCheck } from "lucide-react";

const TRUST_ITEMS = [
  {
    icon: CheckCheck,
    text: "End-to-end encrypted messaging",
  },
  {
    icon: FileCheck2,
    text: "Signed and verifiable files",
  },
  {
    icon: ShieldCheck,
    text: "Verified user-to-user connections",
  },
];

export default function AuthHero() {
  return (
    <section className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900 p-7 md:p-10">
      <div className="pointer-events-none absolute -left-16 -top-16 h-56 w-56 rounded-full bg-cyan-400/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 -right-14 h-64 w-64 rounded-full bg-violet-500/25 blur-3xl" />

      <div className="relative z-10">
        <p className="inline-flex rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs font-medium text-cyan-100">
          CurveEd25519
        </p>

        <h1 className="mt-4 text-3xl font-semibold leading-tight text-white md:text-5xl">
          Private by Design.
          <br />
          Trusted in Every Message.
        </h1>

        <p className="mt-4 max-w-xl text-sm leading-relaxed text-slate-200/90 md:text-base">
          Encrypted conversations, verified identities, secure file sharing, and digital signatures
          built for people who care about privacy.
        </p>

        <div className="mt-7 space-y-3">
          {TRUST_ITEMS.map((item) => (
            <div key={item.text} className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100">
              <item.icon size={16} className="text-cyan-300" />
              <span>{item.text}</span>
            </div>
          ))}
        </div>

        <div className="mt-7 grid grid-cols-2 gap-3">
          <div className="rounded-2xl border border-white/10 bg-black/25 p-3 backdrop-blur">
            <div className="text-xs text-slate-300">Encryption</div>
            <div className="mt-1 text-sm font-medium text-white">X25519 + ChaCha20-Poly1305</div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/25 p-3 backdrop-blur">
            <div className="text-xs text-slate-300">Signatures</div>
            <div className="mt-1 text-sm font-medium text-white">Ed25519 verified</div>
          </div>
        </div>
      </div>
    </section>
  );
}


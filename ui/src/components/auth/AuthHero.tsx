"use client";

import React from "react";
import { FileCheck2, Fingerprint, MessageSquareLock, ShieldCheck } from "lucide-react";

const TRUST_ITEMS = [
  { icon: MessageSquareLock, text: "End-to-end encrypted messaging" },
  {
    icon: FileCheck2,
    text: "Signed and verifiable files",
  },
  {
    icon: Fingerprint,
    text: "Verified user-to-user connections",
  },
];

export default function AuthHero() {
  return (
    <section className="relative flex flex-col justify-between overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900 p-7 md:p-10">
      <div className="pointer-events-none absolute -left-16 -top-16 h-56 w-56 rounded-full bg-cyan-400/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 -right-14 h-64 w-64 rounded-full bg-violet-500/25 blur-3xl" />

      <div className="relative z-10">
        <p className="inline-flex rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs font-medium text-cyan-100">
          CurveEd25519
        </p>

        <h1 className="mt-4 text-4xl font-bold leading-tight tracking-tight text-white md:text-5xl xl:text-6xl">
          Private conversations.
          <br />
          <span className="bg-gradient-to-r from-cyan-300 via-blue-400 to-violet-400 bg-clip-text text-transparent">
            Proven cryptography.
          </span>
        </h1>

        <p className="mt-4 max-w-xl text-sm leading-relaxed text-slate-200/90 md:text-base">
          Secure, end-to-end encrypted messaging with file transfer and digital signatures.
        </p>

        <div className="mt-7 space-y-3">
          {TRUST_ITEMS.map((item) => (
            <div key={item.text} className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100">
              <item.icon size={16} className="text-cyan-300" />
              <span>{item.text}</span>
            </div>
          ))}
        </div>

        <div className="mt-6 inline-flex items-center gap-2 rounded-full border border-emerald-300/30 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-100">
          <ShieldCheck size={13} />
          Built for privacy. Designed for trust.
        </div>

        <div className="relative mx-auto mt-8 h-[320px] w-full max-w-[520px] rounded-[2rem] border border-white/10 bg-white/[0.03] p-5 shadow-[0_0_80px_rgba(99,102,241,0.25)] backdrop-blur">
          <div className="absolute left-5 top-5 rounded-2xl border border-white/15 bg-slate-900/80 px-3 py-2 text-xs text-slate-200">
            <div className="font-medium">Encrypted Session</div>
            <div className="text-slate-400">X25519 · ChaCha20-Poly1305</div>
          </div>
          <div className="absolute right-5 top-14 rounded-2xl border border-violet-300/20 bg-violet-400/10 px-3 py-2 text-xs text-violet-100">
            Signature verified
          </div>
          <div className="absolute bottom-6 left-1/2 w-[86%] -translate-x-1/2 rounded-3xl border border-white/10 bg-slate-900/70 p-4">
            <div className="mb-3 flex items-center gap-2 text-sm">
              <MessageSquareLock size={16} className="text-cyan-300" />
              <span>Secure message channel</span>
            </div>
            <div className="space-y-2">
              <div className="ml-auto max-w-[75%] rounded-2xl bg-blue-500/30 px-3 py-2 text-xs text-slate-100">Key verified. Start secure exchange.</div>
              <div className="max-w-[72%] rounded-2xl bg-white/10 px-3 py-2 text-xs text-slate-200">Signed file received and validated.</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

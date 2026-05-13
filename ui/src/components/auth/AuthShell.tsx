"use client";

import React from "react";
import AuthHero from "@/components/auth/AuthHero";

export default function AuthShell({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#050816] text-zinc-100">
      <div className="pointer-events-none absolute inset-0">
        <div className="auth-glow-orb absolute -left-24 -top-16 h-72 w-72 rounded-full bg-violet-500/30 blur-3xl" />
        <div className="auth-glow-orb absolute left-1/2 top-1/3 h-80 w-80 -translate-x-1/2 rounded-full bg-blue-500/20 blur-3xl [animation-delay:1.1s]" />
        <div className="auth-glow-orb absolute -bottom-24 right-[-5rem] h-96 w-96 rounded-full bg-indigo-500/30 blur-3xl [animation-delay:2s]" />
      </div>

      <main className="relative z-10 mx-auto grid min-h-screen w-full max-w-7xl grid-cols-1 gap-8 px-4 py-6 sm:px-6 sm:py-8 lg:grid-cols-[1.1fr_0.9fr] lg:px-10">
        <AuthHero />
        <section className="flex items-center justify-center py-2 lg:items-start lg:pt-[22vh]">{children}</section>
      </main>
    </div>
  );
}

"use client";

import React from "react";

export default function AuthCard({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="w-full max-w-lg rounded-[2rem] border border-white/10 bg-slate-950/70 p-6 shadow-[0_0_80px_rgba(79,70,229,0.35)] backdrop-blur-xl md:p-8">
      {children}
    </div>
  );
}


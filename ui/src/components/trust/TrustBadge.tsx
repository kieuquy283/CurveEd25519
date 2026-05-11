"use client";
import React from "react";
import { TrustLevel } from "@/types/models";

export default function TrustBadge({ level }: { level: TrustLevel | undefined }) {
  const color = level === "trusted" ? "bg-green-600" : level === "verified" ? "bg-blue-600" : "bg-slate-600";
  const label = level === "trusted" ? "Trusted" : level === "verified" ? "Verified" : "Untrusted";

  return (
    <div className={`inline-flex items-center gap-2 px-2 py-1 rounded-full text-xs ${color} text-white`}>
      <span className="w-2 h-2 rounded-full" />
      <span>{label}</span>
    </div>
  );
}

"use client";
import React from "react";
import { generateSafetyNumber } from "@/services/trust";

export default function SafetyNumber({ a, b }: { a?: string; b?: string }) {
  const sn = generateSafetyNumber(a, b);
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-md p-2 text-sm">
      <div className="text-slate-400 text-xs">Safety Number</div>
      <div className="mt-1 font-mono text-sm text-slate-200">{sn}</div>
    </div>
  );
}

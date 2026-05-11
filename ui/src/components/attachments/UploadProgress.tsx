"use client";
import React from "react";

export default function UploadProgress({ progress }: { progress: number }) {
  return (
    <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
      <div
        className="h-2 bg-indigo-600 transition-all"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}

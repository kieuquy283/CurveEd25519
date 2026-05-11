"use client";
import React, { useState } from "react";
import { useContactStore } from "@/store/useContactStore";

export default function ContactSearch() {
  const [q, setQ] = useState("");
  const search = useContactStore((s) => s.searchContacts);

  const results = q.trim() === "" ? [] : search(q);

  return (
    <div className="px-3 py-2">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search contacts"
        className="w-full bg-slate-800 rounded-md px-3 py-2 text-sm focus:outline-none"
      />
      {results.length > 0 && (
        <div className="mt-2 text-slate-400 text-xs">{results.length} result(s)</div>
      )}
    </div>
  );
}

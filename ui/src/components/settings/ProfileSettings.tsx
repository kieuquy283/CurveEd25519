"use client";
import React, { useState } from "react";
import { useSettingsStore } from "@/store/useSettingsStore";

export default function ProfileSettings() {
  const prefs = useSettingsStore((s) => s.prefs);
  const setPrefs = useSettingsStore((s) => s.setPrefs);
  const [name, setName] = useState(prefs.localPeerId);

  const save = () => {
    setPrefs({ localPeerId: name });
  };

  return (
    <div className="p-3">
      <h4 className="font-semibold mb-2">Profile</h4>
      <div className="flex flex-col gap-2">
        <label className="text-sm">Local Peer ID</label>
        <input value={name} onChange={(e) => setName(e.target.value)} className="bg-slate-800 rounded-md px-2 py-1" />
        <div className="flex gap-2 justify-end mt-2">
          <button onClick={save} className="px-3 py-2 bg-indigo-600 rounded-md">Save</button>
        </div>
      </div>
    </div>
  );
}

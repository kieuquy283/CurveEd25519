"use client";
import React, { useState } from "react";
import { useSettingsStore } from "@/store/useSettingsStore";
import { websocketService } from "@/services/websocket";

export default function ConnectionSettings() {
  const prefs = useSettingsStore((s) => s.prefs);
  const setWsEndpoint = useSettingsStore((s) => s.setWsEndpoint);
  const [endpoint, setEndpoint] = useState(prefs.wsEndpoint);
  const [testing, setTesting] = useState(false);

  const apply = async () => {
    setWsEndpoint(endpoint);
    try {
      websocketService.updateConfig({ url: endpoint });
      setTesting(true);
      await websocketService.connect();
    } catch (e) {
      console.error("Failed to connect to WS endpoint:", e);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="p-3">
      <h4 className="font-semibold mb-2">Connection</h4>
      <div className="flex flex-col gap-2">
        <label className="text-sm">WebSocket Endpoint</label>
        <input value={endpoint} onChange={(e) => setEndpoint(e.target.value)} className="bg-slate-800 rounded-md px-2 py-1" />
        <div className="flex gap-2 justify-end mt-2">
          <button onClick={apply} className="px-3 py-2 bg-indigo-600 rounded-md">Apply & Test</button>
        </div>
        {testing && <div className="text-sm text-slate-400 mt-2">Testing connection...</div>}
      </div>
    </div>
  );
}

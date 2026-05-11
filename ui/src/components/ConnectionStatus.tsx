/**
 * Connection status indicator component.
 */

"use client";

import React from "react";
import { Wifi, WifiOff, AlertCircle } from "lucide-react";

interface ConnectionStatusProps {
  connected: boolean;
  error?: string | null;
}

export function ConnectionStatus({ connected, error }: ConnectionStatusProps) {
  if (connected) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 bg-emerald-950 border border-emerald-800 rounded-lg">
        <Wifi size={14} className="text-emerald-400 animate-pulse" />
        <span className="text-xs text-emerald-300 font-medium">Connected</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 bg-red-950 border border-red-800 rounded-lg">
        <AlertCircle size={14} className="text-red-400" />
        <span className="text-xs text-red-300 font-medium">Error</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-yellow-950 border border-yellow-800 rounded-lg">
      <WifiOff size={14} className="text-yellow-400 animate-pulse" />
      <span className="text-xs text-yellow-300 font-medium">Connecting...</span>
    </div>
  );
}

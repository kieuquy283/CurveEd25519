import { create } from "zustand";

import type { CaptureThreat } from "@/components/security/CameraCaptureGuard";

type GuardStatus = "idle" | "loading" | "active" | "error";

interface CameraGuardStore {
  enabled: boolean;
  status: GuardStatus;
  threat: CaptureThreat;
  setEnabled: (enabled: boolean) => void;
  setStatus: (status: GuardStatus) => void;
  setThreat: (threat: CaptureThreat) => void;
}

export const useCameraGuardStore = create<CameraGuardStore>((set) => ({
  enabled: false,
  status: "idle",
  threat: { active: false, level: "none" },
  setEnabled: (enabled) => set({ enabled }),
  setStatus: (status) => set({ status }),
  setThreat: (threat) => set({ threat }),
}));


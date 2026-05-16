"use client";

import React, { memo, useCallback, useEffect, useRef, useState } from "react";

import { useCameraGuardStore } from "@/store/useCameraGuardStore";

export type CaptureThreat = {
  active: boolean;
  label?: string;
  score?: number;
  bbox?: [number, number, number, number];
  level: "none" | "low" | "medium" | "high";
};

export type CameraCaptureGuardProps = {
  conversationId?: string;
  onThreatChange?: (threat: CaptureThreat) => void;
  onAuditEvent?: (event: {
    event_type: "capture_device_detected";
    detected_class?: string;
    score?: number;
    timestamp: string;
    conversation_id?: string;
  }) => Promise<void> | void;
};

type GuardStatus = "idle" | "loading" | "active" | "error";

type CocoPrediction = {
  class: string;
  score: number;
  bbox: [number, number, number, number];
};

const PHONE_THRESHOLD = 0.65;

function sameThreat(a: CaptureThreat, b: CaptureThreat): boolean {
  return a.active === b.active && a.level === b.level && a.label === b.label && a.score === b.score;
}

function CameraCaptureGuardBase({ conversationId, onThreatChange, onAuditEvent }: CameraCaptureGuardProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const modelRef = useRef<{ detect: (input: HTMLVideoElement) => Promise<CocoPrediction[]> } | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<number | null>(null);
  const hitCountRef = useRef(0);
  const clearCountRef = useRef(0);
  const lastThreatActiveRef = useRef(false);
  const isDetectingRef = useRef(false);
  const threatRef = useRef<CaptureThreat>({ active: false, level: "none" });
  const infoRef = useRef<{ label: string; score: number } | null>(null);

  const setStoreEnabled = useCameraGuardStore((s) => s.setEnabled);
  const setStoreStatus = useCameraGuardStore((s) => s.setStatus);
  const setStoreThreat = useCameraGuardStore((s) => s.setThreat);

  const [status, setStatus] = useState<GuardStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [infoDetection, setInfoDetection] = useState<{ label: string; score: number } | null>(null);
  const [threat, setThreat] = useState<CaptureThreat>({ active: false, level: "none" });

  const emitThreat = useCallback(
    (nextThreat: CaptureThreat) => {
      if (sameThreat(threatRef.current, nextThreat)) return;
      threatRef.current = nextThreat;
      setThreat(nextThreat);
      setStoreThreat(nextThreat);
      onThreatChange?.(nextThreat);
      if (nextThreat.active && !lastThreatActiveRef.current) {
        void onAuditEvent?.({
          event_type: "capture_device_detected",
          detected_class: nextThreat.label,
          score: nextThreat.score,
          timestamp: new Date().toISOString(),
          conversation_id: conversationId,
        });
      }
      lastThreatActiveRef.current = nextThreat.active;
    },
    [conversationId, onAuditEvent, onThreatChange, setStoreThreat]
  );

  const cleanupResources = useCallback(() => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.srcObject = null;
    }
    modelRef.current = null;
    isDetectingRef.current = false;
    hitCountRef.current = 0;
    clearCountRef.current = 0;
  }, []);

  const stopGuard = useCallback(() => {
    cleanupResources();
    setStoreEnabled(false);
    setStoreStatus("idle");
    setStatus("idle");
    setErrorMessage(null);
    if (infoRef.current) {
      infoRef.current = null;
      setInfoDetection(null);
    }
    emitThreat({ active: false, level: "none" });
  }, [cleanupResources, emitThreat, setStoreEnabled, setStoreStatus]);

  const runDetection = useCallback(async () => {
    if (isDetectingRef.current) return;
    if (!modelRef.current || !videoRef.current || videoRef.current.readyState < 2) return;

    isDetectingRef.current = true;
    try {
      const predictions = await modelRef.current.detect(videoRef.current);

      let riskyPhone: CocoPrediction | null = null;
      let infoCandidate: { label: string; score: number } | null = null;
      for (const item of predictions) {
        if (item.class === "person") continue;
        if (item.class === "cell phone" && item.score >= PHONE_THRESHOLD) {
          if (!riskyPhone || item.score > riskyPhone.score) riskyPhone = item;
        } else if ((item.class === "laptop" || item.class === "tv") && item.score >= 0.65) {
          if (!infoCandidate || item.score > infoCandidate.score) infoCandidate = { label: item.class, score: item.score };
        }
      }

      const currentInfo = infoRef.current;
      if (!currentInfo && infoCandidate) {
        infoRef.current = infoCandidate;
        setInfoDetection(infoCandidate);
      } else if (currentInfo && !infoCandidate) {
        infoRef.current = null;
        setInfoDetection(null);
      } else if (
        currentInfo &&
        infoCandidate &&
        (currentInfo.label !== infoCandidate.label || Math.round(currentInfo.score * 100) !== Math.round(infoCandidate.score * 100))
      ) {
        infoRef.current = infoCandidate;
        setInfoDetection(infoCandidate);
      }

      if (riskyPhone) {
        hitCountRef.current += 1;
        clearCountRef.current = 0;
      } else {
        clearCountRef.current += 1;
        hitCountRef.current = 0;
      }

      if (hitCountRef.current >= 3 && riskyPhone) {
        emitThreat({
          active: true,
          label: riskyPhone.class,
          score: riskyPhone.score,
          bbox: riskyPhone.bbox,
          level: "high",
        });
      } else if (clearCountRef.current >= 5) {
        emitThreat({ active: false, level: "none" });
      }
    } catch {
      // keep monitoring loop running
    } finally {
      isDetectingRef.current = false;
    }
  }, [emitThreat]);

  const startGuard = useCallback(async () => {
    if (status === "loading" || status === "active") return;
    setStatus("loading");
    setStoreStatus("loading");
    setStoreEnabled(true);
    setErrorMessage(null);
    hitCountRef.current = 0;
    clearCountRef.current = 0;
    emitThreat({ active: false, level: "none" });

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false,
      });
      streamRef.current = stream;

      if (!videoRef.current) throw new Error("camera_not_ready");
      videoRef.current.srcObject = stream;
      await videoRef.current.play();

      const tfjs = await import("@tensorflow/tfjs");
      void tfjs;
      const cocoSsd = await import("@tensorflow-models/coco-ssd");
      modelRef.current = await cocoSsd.load({ base: "lite_mobilenet_v2" });

      setStatus("active");
      setStoreStatus("active");
      intervalRef.current = window.setInterval(() => {
        void runDetection();
      }, 1200);
    } catch (error: unknown) {
      cleanupResources();
      setStoreEnabled(false);
      setStoreStatus("error");
      setStatus("error");
      emitThreat({ active: false, level: "none" });

      let message = "Cannot start camera guard.";
      if (error && typeof error === "object" && "name" in error) {
        const name = String(error.name);
        if (name === "NotAllowedError") message = "Camera permission denied.";
        else if (name === "NotFoundError") message = "No camera device found.";
        else if (name === "NotReadableError") message = "Camera is busy or blocked by another app.";
      }
      setErrorMessage(message);
    }
  }, [cleanupResources, emitThreat, runDetection, setStoreEnabled, setStoreStatus, status]);

  useEffect(() => {
    return () => {
      cleanupResources();
      setStoreEnabled(false);
      setStoreStatus("idle");
      setStoreThreat({ active: false, level: "none" });
      onThreatChange?.({ active: false, level: "none" });
    };
  }, [cleanupResources, onThreatChange, setStoreEnabled, setStoreStatus, setStoreThreat]);

  const statusText =
    status === "loading"
      ? "Loading"
      : threat.active && threat.level === "high"
        ? "Phone detected"
        : status === "active"
          ? "Monitoring"
          : "Local only";

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-2.5">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => {
            if (status === "active" || status === "loading") stopGuard();
            else void startGuard();
          }}
          className={`rounded-xl border px-2.5 py-1.5 text-[11px] font-medium ${
            status === "active" || status === "loading"
              ? "border-emerald-400/35 bg-emerald-500/15 text-emerald-200"
              : "border-zinc-500/40 bg-zinc-600/20 text-zinc-200"
          }`}
        >
          {status === "active" || status === "loading" ? "Camera Guard: On" : "Camera Guard: Off"}
        </button>
        <span className="text-[10px] text-zinc-400">{statusText}</span>
      </div>

      {status === "idle" || status === "error" ? (
        <p className="mt-2 text-[10px] text-zinc-400">Camera Guard is disabled. Camera will not be used.</p>
      ) : (
        <p className="mt-2 text-[10px] text-zinc-400">Camera is processed locally. No video or image is uploaded.</p>
      )}

      {status === "error" && <p className="mt-1 text-[10px] text-rose-300">{errorMessage}</p>}
      {infoDetection && !threat.active && (
        <p className="mt-1 text-[10px] text-amber-300">
          Info: {infoDetection.label} ({Math.round(infoDetection.score * 100)}%)
        </p>
      )}

      {(status === "active" || status === "loading") && (
        <button
          type="button"
          onClick={() => setShowPreview((v) => !v)}
          className="mt-1 text-[10px] text-zinc-300 underline-offset-2 hover:underline"
        >
          {showPreview ? "Hide preview" : "Show preview"}
        </button>
      )}

      <video
        ref={videoRef}
        className={showPreview && status === "active" ? "mt-2 h-20 w-32 rounded-md border border-white/15 object-cover" : "hidden"}
        muted
        playsInline
      />
    </div>
  );
}

export const CameraCaptureGuard = memo(CameraCaptureGuardBase);


"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";

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
const INFO_THRESHOLDS: Record<string, number> = {
  laptop: 0.65,
  tv: 0.65,
};

export function CameraCaptureGuard({ conversationId, onThreatChange, onAuditEvent }: CameraCaptureGuardProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const modelRef = useRef<{ detect: (input: HTMLVideoElement) => Promise<CocoPrediction[]> } | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<number | null>(null);
  const hitCountRef = useRef(0);
  const clearCountRef = useRef(0);
  const lastThreatActiveRef = useRef(false);
  const isDetectingRef = useRef(false);

  const [status, setStatus] = useState<GuardStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(true);
  const [threat, setThreat] = useState<CaptureThreat>({ active: false, level: "none" });
  const [infoDetection, setInfoDetection] = useState<{ label: string; score: number } | null>(null);

  const emitThreat = useCallback(
    (nextThreat: CaptureThreat) => {
      setThreat(nextThreat);
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
    [conversationId, onAuditEvent, onThreatChange]
  );

  const stopGuard = useCallback(() => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    hitCountRef.current = 0;
    clearCountRef.current = 0;
    isDetectingRef.current = false;
    modelRef.current = null;
    setInfoDetection(null);

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.srcObject = null;
    }

    setErrorMessage(null);
    emitThreat({ active: false, level: "none" });
    setStatus("idle");
  }, [emitThreat]);

  const runDetection = useCallback(async () => {
    if (isDetectingRef.current) return;
    if (!modelRef.current || !videoRef.current || videoRef.current.readyState < 2) return;

    isDetectingRef.current = true;
    try {
      const predictions = await modelRef.current.detect(videoRef.current);

      let riskyPhone: CocoPrediction | null = null;
      let infoRisk: CocoPrediction | null = null;

      for (const item of predictions) {
        if (item.class === "person") continue;
        if (item.class === "cell phone" && item.score >= PHONE_THRESHOLD) {
          if (!riskyPhone || item.score > riskyPhone.score) riskyPhone = item;
          continue;
        }
        const infoThreshold = INFO_THRESHOLDS[item.class];
        if (infoThreshold !== undefined && item.score >= infoThreshold) {
          if (!infoRisk || item.score > infoRisk.score) infoRisk = item;
        }
      }

      setInfoDetection(infoRisk ? { label: infoRisk.class, score: infoRisk.score } : null);

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
      // keep guard running if one cycle fails
    } finally {
      isDetectingRef.current = false;
    }
  }, [emitThreat]);

  const startGuard = useCallback(async () => {
    if (status === "loading" || status === "active") return;
    setStatus("loading");
    setErrorMessage(null);
    hitCountRef.current = 0;
    clearCountRef.current = 0;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false,
      });
      streamRef.current = stream;

      if (!videoRef.current) throw new Error("Camera preview not ready");
      videoRef.current.srcObject = stream;
      await videoRef.current.play();

      const tfjs = await import("@tensorflow/tfjs");
      void tfjs;
      const cocoSsd = await import("@tensorflow-models/coco-ssd");
      modelRef.current = await cocoSsd.load({ base: "lite_mobilenet_v2" });

      setStatus("active");
      intervalRef.current = window.setInterval(() => {
        void runDetection();
      }, 900);
    } catch (error: unknown) {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
      if (videoRef.current) videoRef.current.srcObject = null;

      let message = "Cannot start camera guard.";
      if (error && typeof error === "object" && "name" in error) {
        const name = String(error.name);
        if (name === "NotAllowedError") message = "Camera permission denied.";
        else if (name === "NotFoundError") message = "No camera device found.";
        else if (name === "NotReadableError") message = "Camera is busy or blocked by another app.";
      }
      setErrorMessage(message);
      setStatus("error");
      emitThreat({ active: false, level: "none" });
    }
  }, [emitThreat, runDetection, status]);

  useEffect(() => {
    return () => {
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
      hitCountRef.current = 0;
      clearCountRef.current = 0;
      modelRef.current = null;
      setInfoDetection(null);
      onThreatChange?.({ active: false, level: "none" });
    };
  }, [onThreatChange]);

  const statusText =
    status === "loading"
      ? "Loading model"
      : threat.active && threat.level === "high"
        ? "Threat detected"
        : status === "active"
          ? "Monitoring"
          : "OFF";

  return (
    <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-3">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => {
            if (status === "active" || status === "loading") stopGuard();
            else void startGuard();
          }}
          className="rounded-xl border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-semibold text-zinc-200 hover:bg-white/10"
        >
          {status === "active" || status === "loading" ? "Disable Camera Guard" : "Enable Camera Guard"}
        </button>
        <span className="text-xs text-zinc-300">{statusText}</span>
      </div>

      {status === "idle" || status === "error" ? (
        <p className="mt-2 text-xs text-zinc-400">Camera Guard is disabled. Camera will not be used.</p>
      ) : (
        <p className="mt-2 text-xs text-zinc-400">Camera is processed locally. No video or image is uploaded.</p>
      )}

      {status === "error" && <p className="mt-2 text-xs text-rose-300">{errorMessage}</p>}

      {status === "active" && (
        <button
          type="button"
          onClick={() => setShowPreview((v) => !v)}
          className="mt-2 rounded-xl border border-white/15 bg-white/5 px-2.5 py-1 text-xs text-zinc-300 hover:bg-white/10"
        >
          {showPreview ? "Hide preview" : "Show preview"}
        </button>
      )}

      <video
        ref={videoRef}
        className={showPreview && status === "active" ? "mt-3 h-24 w-40 rounded-lg border border-white/15 object-cover" : "hidden"}
        muted
        playsInline
      />

      {infoDetection && !threat.active && (
        <div className="mt-3 rounded-lg border border-amber-300/30 bg-amber-500/10 p-2 text-xs text-amber-100">
          Info: {infoDetection.label} ({Math.round(infoDetection.score * 100)}%)
        </div>
      )}

      {threat.active && threat.level === "high" && (
        <div className="mt-3 rounded-lg border border-rose-400/40 bg-rose-500/15 p-2 text-xs text-rose-100">
          <div className="font-semibold">Possible external recording device detected.</div>
          <div className="mt-1">
            {threat.label || "cell phone"} {typeof threat.score === "number" ? `(${Math.round(threat.score * 100)}%)` : ""}
          </div>
        </div>
      )}
    </div>
  );
}

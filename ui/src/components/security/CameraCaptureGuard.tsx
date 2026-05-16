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

const LOW_CLASS = "person";

const RISK_THRESHOLDS: Record<string, number> = {
  "cell phone": 0.55,
  camera: 0.55,
  laptop: 0.65,
  tv: 0.65,
  person: 0.75,
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

  const findHighestRisk = (predictions: CocoPrediction[]): CaptureThreat | null => {
    let picked: CocoPrediction | null = null;
    for (const item of predictions) {
      const threshold = RISK_THRESHOLDS[item.class];
      if (threshold === undefined || item.score < threshold) continue;
      if (!picked || item.score > picked.score) picked = item;
    }
    if (!picked) return null;

    const level: CaptureThreat["level"] = picked.class === LOW_CLASS ? "low" : picked.score >= 0.8 ? "high" : "medium";
    return {
      active: true,
      label: picked.class,
      score: picked.score,
      bbox: picked.bbox,
      level,
    };
  };

  const runDetection = useCallback(async () => {
    if (isDetectingRef.current) return;
    if (!modelRef.current || !videoRef.current || videoRef.current.readyState < 2) return;

    isDetectingRef.current = true;
    try {
      const predictions = await modelRef.current.detect(videoRef.current);
      const risk = findHighestRisk(predictions);

      if (risk) {
        hitCountRef.current += 1;
        clearCountRef.current = 0;
      } else {
        clearCountRef.current += 1;
        hitCountRef.current = 0;
      }

      if (hitCountRef.current >= 3) {
        emitThreat(risk || { active: true, level: "low" });
      } else if (clearCountRef.current >= 5) {
        emitThreat({ active: false, level: "none" });
      }
    } catch {
      // keep guard running even if one inference cycle fails
    } finally {
      isDetectingRef.current = false;
    }
  }, [emitThreat]);

  const startGuard = useCallback(async () => {
    if (status === "loading" || status === "active") return;
    setStatus("loading");
    setErrorMessage(null);

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
    };
  }, []);

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
          Camera guard
        </button>
        {status === "active" && (
          <button
            type="button"
            onClick={() => setShowPreview((v) => !v)}
            className="rounded-xl border border-white/15 bg-white/5 px-2.5 py-1 text-xs text-zinc-300 hover:bg-white/10"
          >
            {showPreview ? "Hide preview" : "Show preview"}
          </button>
        )}
      </div>

      <p className="mt-2 text-xs text-zinc-400">
        Camera is processed locally. No video, image, or frame is stored or uploaded.
      </p>

      {status === "loading" && <p className="mt-2 text-xs text-amber-300">Loading camera + model...</p>}
      {status === "error" && <p className="mt-2 text-xs text-rose-300">{errorMessage}</p>}

      <video
        ref={videoRef}
        className={showPreview && status === "active" ? "mt-3 h-24 w-40 rounded-lg border border-white/15 object-cover" : "hidden"}
        muted
        playsInline
      />

      {threat.active && (
        <div className="mt-3 rounded-lg border border-rose-400/40 bg-rose-500/15 p-2 text-xs text-rose-100">
          <div className="font-semibold">Possible external recording device detected.</div>
          <div className="mt-1">
            {threat.label || "unknown"} {typeof threat.score === "number" ? `(${Math.round(threat.score * 100)}%)` : ""}
          </div>
        </div>
      )}
    </div>
  );
}

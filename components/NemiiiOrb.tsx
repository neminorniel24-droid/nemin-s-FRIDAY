"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createOrbScene, type OrbSceneApi } from "@/lib/orbScene";
import { HandTracker, type TrackerStatus, type SwipeDirection } from "@/lib/handTracker";
import { VoiceAssistant, type VoiceState, type VoiceAssistantHandle } from "@/components/VoiceAssistant";
import { InfoDashboard } from "@/components/InfoDashboard";
import { VrmAvatar, type VrmAvatarHandle, type AvatarState } from "@/components/VrmAvatar";

type CameraState = "off" | "starting" | "on" | "error";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const MODE_LABEL: Record<TrackerStatus["mode"], string> = {
  idle: "IDLE",
  spin: "SPIN",
  zoom: "ZOOM",
};

export default function NemiiiOrb() {
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const sceneRef = useRef<OrbSceneApi | null>(null);
  const trackerRef = useRef<HandTracker | null>(null);
  const voiceRef = useRef<VoiceAssistantHandle>(null);
  const vrmHandleRef = useRef<VrmAvatarHandle>(null);

  const [camera, setCamera] = useState<CameraState>("off");
  const [status, setStatus] = useState<TrackerStatus>({ hands: 0, mode: "idle" });
  const [error, setError] = useState<string | null>(null);
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");

  const [avatarMode, setAvatarMode] = useState(false);
  const [containerEl, setContainerEl] = useState<HTMLDivElement | null>(null);

  const setContainerRef = useCallback((el: HTMLDivElement | null) => {
    containerRef.current = el;
    setContainerEl(el);
  }, []);

  const handleSwipe = useCallback((direction: SwipeDirection) => {
    const action =
      direction === "down"
        ? { type: "minimize_all", arg: "" }
        : { type: "switch_tab", arg: direction === "right" ? "next" : "previous" };

    fetch(`${BACKEND_URL}/gesture_action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(action),
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (avatarMode) return;
    const container = containerRef.current;
    if (!container) return;
    const scene = createOrbScene(container);
    sceneRef.current = scene;
    return () => {
      trackerRef.current?.stop();
      trackerRef.current = null;
      scene.dispose();
      sceneRef.current = null;
    };
  }, [avatarMode]);

  useEffect(() => {
    const timer = setTimeout(() => {
      voiceRef.current?.greet();
    }, 1500);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!avatarMode) return;
    const mapped: AvatarState =
      voiceState === "listening" || voiceState === "thinking" || voiceState === "speaking"
        ? voiceState
        : "idle";
    vrmHandleRef.current?.setState(mapped);
  }, [voiceState, avatarMode]);

  const startGestures = useCallback(async () => {
    const video = videoRef.current;
    const overlay = overlayRef.current;
    if (!video || !overlay || trackerRef.current) return;

    setCamera("starting");
    setError(null);

    const tracker = new HandTracker(video, overlay, {
      onRotate: (dt, dp) => sceneRef.current?.rotateBy(dt, dp),
      onZoom: (factor) => sceneRef.current?.zoomBy(factor),
      onDoubleTap: () => voiceRef.current?.greet(),
      onSwipe: handleSwipe,
      onStatus: setStatus,
    });
    trackerRef.current = tracker;

    try {
      await tracker.start();
      setCamera("on");
    } catch (err) {
      trackerRef.current = null;
      setCamera("error");
      setError(err instanceof Error ? err.message : "Couldn't access the camera");
    }
  }, [handleSwipe]);

  const stopGestures = useCallback(() => {
    trackerRef.current?.stop();
    trackerRef.current = null;
    setCamera("off");
    setStatus({ hands: 0, mode: "idle" });
  }, []);

  const toggleGestures = useCallback(() => {
    if (trackerRef.current) stopGestures();
    else void startGestures();
  }, [startGestures, stopGestures]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      switch (e.key) {
        case "g":
        case "G":
          toggleGestures();
          break;
        case "v":
        case "V":
          voiceRef.current?.toggleListening();
          break;
        case "r":
        case "R":
          sceneRef.current?.resetView();
          break;
        case "+":
        case "=":
          sceneRef.current?.zoomIn();
          break;
        case "-":
        case "_":
          sceneRef.current?.zoomOut();
          break;
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [toggleGestures]);

  const cameraOn = camera === "on";

  return (
    <>
      <div ref={setContainerRef} className={`orb-root${voiceState !== "idle" && voiceState !== "error" ? ` voice-${voiceState}` : ""}`}>
        {avatarMode && containerEl && <VrmAvatar ref={vrmHandleRef} container={containerEl} />}
      </div>

      <video ref={videoRef} className="camera-feed" autoPlay playsInline muted style={{ display: cameraOn ? "block" : "none" }} />
      <canvas ref={overlayRef} className="camera-overlay" style={{ display: cameraOn ? "block" : "none" }} />

      <div className="hud hud-title">
        N.E.M.I.I.I.
        <div className="hud-subtitle">VOICE-CONTROLLED PC ASSISTANT</div>
      </div>

      <InfoDashboard />

      <div className="hud hud-hint">
        <div>
          <span className="key">DRAG</span> spin&nbsp;&nbsp;
          <span className="key">SCROLL</span> zoom
        </div>
        {cameraOn ? (
          <div>
            <span className="key">PINCH + MOVE</span> spin&nbsp;&nbsp;
            <span className="key">PINCH BOTH HANDS ± SPREAD</span> zoom&nbsp;&nbsp;
            <span className="key">PINCH TWICE</span> greet&nbsp;&nbsp;
            <span className="key">OPEN HAND SWIPE ←/→</span> switch tab&nbsp;&nbsp;
            <span className="key">OPEN HAND SWIPE ↓</span> minimize all
          </div>
        ) : (
          <div>
            <span className="key">G</span> hand gestures&nbsp;&nbsp;
            <span className="key">V</span> voice&nbsp;&nbsp;
            <span className="key">R</span> reset&nbsp;&nbsp;
            <span className="key">+/−</span> zoom&nbsp;&nbsp;
            <span className="key">SAY "COME HERE"</span> summon avatar
          </div>
        )}
      </div>

      <div className="hud hud-controls">
        <VoiceAssistant ref={voiceRef} onStateChange={setVoiceState} onSummonPhrase={() => setAvatarMode(true)} />

        {avatarMode && (
          <button type="button" className="hud-btn" onClick={() => setAvatarMode(false)}>
            BACK TO ORB
          </button>
        )}

        <div className={`camera-panel${cameraOn ? " visible" : ""}`}>
          <div className="hud-row">
            <span>HANDS: {status.hands}</span>
            <span>MODE: {MODE_LABEL[status.mode]}</span>
          </div>
        </div>

        {error && <div className="hud-error">{error}</div>}

        <button type="button" className="hud-btn" onClick={toggleGestures} aria-pressed={cameraOn}>
          {camera === "starting" ? "STARTING…" : cameraOn ? "GESTURES ON" : "GESTURES OFF"}
        </button>

        <div className="hud-row">
          <button type="button" className="hud-btn small" onClick={() => sceneRef.current?.zoomIn()}>
            +
          </button>
          <button type="button" className="hud-btn small" onClick={() => sceneRef.current?.zoomOut()}>
            −
          </button>
          <button type="button" className="hud-btn small" onClick={() => sceneRef.current?.resetView()}>
            RESET
          </button>
        </div>
      </div>
    </>
  );
}

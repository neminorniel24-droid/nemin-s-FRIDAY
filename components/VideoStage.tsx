"use client";
// Your own video, full screen, NEVER stretched.
//
// How: the <video> fills its box and CSS object-fit:contain keeps the true shape
// of the picture (the browser adds empty black space instead of distorting it).
// Your video has a black background anyway, so the empty space is invisible.
//
// While she talks the picture leans in slowly (a small zoom). Change ZOOM below,
// or set a state to 1 to turn it off. Press D to see the debug numbers.
import { useEffect, useRef, useState } from "react";
import type { AvatarState } from "@/lib/types";

const VIDEO_URL = "/nemiii-video.mp4"; // put your video at public/nemiii-video.mp4

const LOOK: Record<AvatarState, { zoom: number; brightness: number }> = {
  idle: { zoom: 1.0, brightness: 0.85 },
  listening: { zoom: 1.0, brightness: 1.0 },
  thinking: { zoom: 1.0, brightness: 0.65 },
  speaking: { zoom: 1.04, brightness: 1.05 },
};

export default function VideoStage({ state }: { state: AvatarState }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [failed, setFailed] = useState(false);
  const [debug, setDebug] = useState(false);
  const [info, setInfo] = useState("");

  useEffect(() => {
    ref.current?.play().catch(() => {});
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (e.key.toLowerCase() === "d" && tag !== "INPUT" && tag !== "SELECT") setDebug((d) => !d);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!debug) return;
    const id = setInterval(() => {
      const v = ref.current;
      if (!v) return;
      const r = v.getBoundingClientRect();
      const fit = getComputedStyle(v).objectFit;
      setInfo(
        `video file ${v.videoWidth}x${v.videoHeight} (ratio ${(v.videoWidth / v.videoHeight || 0).toFixed(3)})\n` +
          `box on screen ${Math.round(r.width)}x${Math.round(r.height)}\n` +
          `object-fit: ${fit}   time: ${v.currentTime.toFixed(1)}s`,
      );
    }, 400);
    return () => clearInterval(id);
  }, [debug]);

  const look = LOOK[state];
  return (
    <div className="video-stage">
      <div className="video-zoom" style={{ transform: `scale(${look.zoom})`, filter: `brightness(${look.brightness})` }}>
        <video ref={ref} className="video-el" src={VIDEO_URL} autoPlay loop muted playsInline onError={() => setFailed(true)} />
      </div>
      {failed && (
        <div className="video-missing">
          Video not found.<br />Put your video file at <b>public/nemiii-video.mp4</b> and refresh.
        </div>
      )}
      {debug && <pre className="video-debug">{info}</pre>}
    </div>
  );
}

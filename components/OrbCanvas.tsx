"use client";
// The original Nemiii orb (see lib/orbScene.ts). Drag to spin, scroll to zoom.
// Keys here: R reset view, + / - zoom.
import { memo, useEffect, useRef } from "react";
import { createOrbScene, type OrbSceneApi } from "@/lib/orbScene";
import type { AvatarState } from "@/lib/types";

function OrbCanvas({ state }: { state: AvatarState }) {
  const host = useRef<HTMLDivElement>(null);
  const api = useRef<OrbSceneApi | null>(null);
  const stateRef = useRef<AvatarState>(state);
  stateRef.current = state;

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const scene = createOrbScene(el);
    api.current = scene;
    scene.setState(stateRef.current);

    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "r" || e.key === "R") scene.resetView();
      else if (e.key === "+" || e.key === "=") scene.zoomIn();
      else if (e.key === "-" || e.key === "_") scene.zoomOut();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      scene.dispose();
      api.current = null;
    };
  }, []);

  useEffect(() => {
    api.current?.setState(state);
  }, [state]);

  return <div ref={host} style={{ position: "fixed", inset: 0, background: "#000", cursor: "grab" }} />;
}

export default memo(OrbCanvas);

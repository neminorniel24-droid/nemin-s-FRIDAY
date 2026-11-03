"use client";
// The Nemiii orb (see lib/orbScene.ts). Drag to spin, scroll to zoom. Keys: R reset view, + / - zoom.
// It re-builds itself when the theme changes, and pulses with your voice when `getLevel` is given.
import { memo, useEffect, useRef } from "react";
import { createOrbScene, type OrbSceneApi } from "@/lib/orbScene";
import { THEMES, type ThemeKey } from "@/lib/themes";
import type { AvatarState } from "@/lib/types";

interface Props {
  state: AvatarState;
  theme?: ThemeKey;
  getLevel?: (() => number) | null;
  keys?: boolean;
}

function OrbCanvas({ state, theme = "peacock", getLevel = null, keys = true }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const api = useRef<OrbSceneApi | null>(null);
  const stateRef = useRef<AvatarState>(state);
  stateRef.current = state;
  const levelRef = useRef(getLevel);
  levelRef.current = getLevel;

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const scene = createOrbScene(el, THEMES[theme]);
    api.current = scene;
    scene.setState(stateRef.current);
    scene.setLevelSource(() => (levelRef.current ? levelRef.current() : 0));

    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (!keys || tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || e.ctrlKey || e.metaKey || e.altKey) return;
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
  }, [theme, keys]);

  useEffect(() => {
    api.current?.setState(state);
  }, [state]);

  return <div ref={host} style={{ position: "fixed", inset: 0, background: "#000", cursor: "grab" }} />;
}

export default memo(OrbCanvas);

"use client";
// A small floating copy of the orb. Open it with the MINI button or by saying "mini orb".
// It follows the main window (state + theme) through a BroadcastChannel. To keep it above other
// windows, press Win + Ctrl + T on it (PowerToys "Always on Top"). Double-click to bring the main window forward.
import { useEffect, useState } from "react";
import OrbCanvas from "./OrbCanvas";
import { applyTheme, isTheme, type ThemeKey } from "@/lib/themes";
import type { AvatarState } from "@/lib/types";

export default function MiniOrb() {
  const [state, setState] = useState<AvatarState>("idle");
  const [theme, setTheme] = useState<ThemeKey>("peacock");
  const [alive, setAlive] = useState(false);

  useEffect(() => {
    document.title = "NEMIII mini";
    let last = 0;
    const ch = new BroadcastChannel("nemiii");
    ch.onmessage = (e) => {
      const m = e.data || {};
      last = Date.now();
      setAlive(true);
      if (m.state) setState(m.state);
      if (isTheme(m.theme)) {
        setTheme(m.theme);
        applyTheme(m.theme);
      }
    };
    ch.postMessage({ hello: true }); // ask the main window to send its current look
    const id = setInterval(() => setAlive(Date.now() - last < 6000), 2000);
    return () => {
      clearInterval(id);
      ch.close();
    };
  }, []);

  return (
    <div onDoubleClick={() => { try { window.opener?.focus(); } catch { /* ignore */ } }}>
      <OrbCanvas state={state} theme={theme} keys={false} />
      {!alive && (
        <div style={{ position: "fixed", left: 0, right: 0, bottom: 8, textAlign: "center", fontSize: 10, letterSpacing: 2, color: "var(--dim)", pointerEvents: "none" }}>
          WAITING FOR NEMIII
        </div>
      )}
    </div>
  );
}

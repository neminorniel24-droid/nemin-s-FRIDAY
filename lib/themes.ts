// Colour themes. Say "theme red" / "red alert" / "gold" / "ice" / "peacock", or press T.
// To add your own: copy one block, change the colours, add its name to THEME_ORDER.

export type ThemeKey = "peacock" | "red" | "gold" | "ice";

export interface Theme {
  label: string;
  css: Record<string, string>;      // page colours
  orb: { bright: number; mid: number; dim: number; faint: number; hot: number };
  fringe: { tint: [number, number, number]; blue: number }; // the slight colour fringe of the orb
}

export const THEMES: Record<ThemeKey, Theme> = {
  peacock: {
    label: "PEACOCK",
    css: { bg: "#020b0a", main: "#14e0c0", mid: "#0d9488", deep: "#0a3a35", accent: "#7dfff0", text: "#bff7ee",
      "main-rgb": "20,224,192", "deep-rgb": "2,20,18" },
    orb: { bright: 0x14e0c0, mid: 0x0d9488, dim: 0x0f5e56, faint: 0x0a3a35, hot: 0x7dfff0 },
    fringe: { tint: [1.15, 0.85, 0.55], blue: 0.6 }, // the original look
  },
  red: {
    label: "RED ALERT",
    css: { bg: "#0b0202", main: "#ff4d4d", mid: "#b91c1c", deep: "#4a0f0f", accent: "#ffb3a8", text: "#ffd9d4",
      "main-rgb": "255,77,77", "deep-rgb": "30,4,4" },
    orb: { bright: 0xff4d4d, mid: 0xb91c1c, dim: 0x7f1d1d, faint: 0x3d0f0f, hot: 0xffc4b8 },
    fringe: { tint: [1.05, 1, 1], blue: 1 },
  },
  gold: {
    label: "GOLD",
    css: { bg: "#0b0802", main: "#f5b301", mid: "#b07d00", deep: "#4a3500", accent: "#ffe08a", text: "#fff1c9",
      "main-rgb": "245,179,1", "deep-rgb": "28,20,2" },
    orb: { bright: 0xf5b301, mid: 0xb07d00, dim: 0x7a5600, faint: 0x3d2c00, hot: 0xffe08a },
    fringe: { tint: [1.05, 1, 0.9], blue: 1 },
  },
  ice: {
    label: "ICE",
    css: { bg: "#02070d", main: "#4db8ff", mid: "#1d78c8", deep: "#0b2f55", accent: "#bfe8ff", text: "#d9f1ff",
      "main-rgb": "77,184,255", "deep-rgb": "3,16,32" },
    orb: { bright: 0x4db8ff, mid: 0x1d78c8, dim: 0x155a96, faint: 0x0b2f55, hot: 0xbfe8ff },
    fringe: { tint: [0.95, 1, 1.05], blue: 1 },
  },
};

export const THEME_ORDER: ThemeKey[] = ["peacock", "red", "gold", "ice"];

export function isTheme(k: unknown): k is ThemeKey {
  return typeof k === "string" && k in THEMES;
}

export function applyTheme(key: ThemeKey) {
  const root = document.documentElement;
  for (const [k, v] of Object.entries(THEMES[key].css)) root.style.setProperty("--" + k, v);
  root.style.setProperty("--dim", `rgba(${THEMES[key].css["main-rgb"]},0.55)`);
}

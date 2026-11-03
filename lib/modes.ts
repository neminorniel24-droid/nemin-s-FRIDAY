// Turns what you said into an intent. Edit the phrase lists to change the words she reacts to.

// Every name that wakes her. Jarvis, Friday and Edith also switch her personality (see personas.py).
export const WAKE_NAMES = ["nemiii+", "nemi+", "nemy", "nemmy", "nemmi", "nammy", "nami", "jarvis", "friday", "edith"];
const NAME_ALT = WAKE_NAMES.join("|");
export const WAKE_RE = new RegExp(`\\b(${NAME_ALT})\\b`, "i");
const LEAD_RE = new RegExp(`^\\s*(?:hey|hi|hello|ok|okay)?[\\s,]*(${NAME_ALT})\\b[\\s,.!?:-]*`, "i");

const VIDEO = ["come here", "show yourself", "anime mode", "show anime", "show video", "video mode"];
const ORB = ["back to orb", "go back to orb", "show orb", "orb mode", "hide video", "hide anime", "go back to the orb"];
const STOP = ["stop", "be quiet", "quiet", "shut up", "stop talking", "that's enough", "enough"];
const CAMERA = ["what do you see", "what can you see", "look at me", "look at this", "what am i holding",
  "what is this", "what's this", "see this", "look at the camera", "use the camera"];
const SCREEN = ["look at my screen", "what's on my screen", "what is on my screen", "read my screen",
  "see my screen", "look at the screen", "what am i looking at", "explain my screen"];
const PANEL = ["show history", "open history", "open the panel", "show the panel", "open panel", "show my reminders",
  "show the log", "show activity"];
const PANEL_CLOSE = ["close the panel", "hide the panel", "close panel", "hide history", "close history"];
const GALLERY = ["show my creations", "show creations", "show the gallery", "open the gallery", "show gallery", "show what you made",
  "show me what you made", "show my pictures", "show my images", "show my music"];
const GALLERY_CLOSE = ["close the gallery", "hide the gallery", "close gallery", "close creations", "hide creations"];
const MINI = ["mini orb", "floating orb", "small orb", "open the mini orb", "mini mode"];

export type Intent =
  | { type: "mode"; mode: "orb" | "video" }
  | { type: "stop" }
  | { type: "panel"; open: boolean }
  | { type: "mini" }
  | { type: "gallery"; open: boolean }
  | { type: "vision"; source: "camera" | "screen"; question: string }
  | { type: "chat"; text: string };

export function norm(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9' ]+/g, " ").replace(/\s+/g, " ").trim();
}

/** Remove "hey nemiii," style wake words from the front of a sentence. */
export function stripWake(s: string): string {
  return s.replace(LEAD_RE, "").trim();
}

/** Which mode name did you call her by? "Jarvis, open chrome" -> "jarvis". Nemiii-style names return null. */
export function calledPersona(s: string): string | null {
  const m = s.match(LEAD_RE);
  const w = (m?.[1] || "").toLowerCase();
  return w === "jarvis" || w === "friday" || w === "edith" ? w : null;
}

const has = (t: string, list: string[]) => list.some((p) => t.includes(p));

export function classify(raw: string): Intent {
  const text = stripWake(raw);
  const t = norm(text);
  if (has(t, ORB)) return { type: "mode", mode: "orb" };
  if (has(t, VIDEO)) return { type: "mode", mode: "video" };
  if (t.length < 22 && STOP.some((p) => t === p || t.startsWith(p + " "))) return { type: "stop" };
  if (has(t, GALLERY_CLOSE)) return { type: "gallery", open: false };
  if (has(t, GALLERY)) return { type: "gallery", open: true };
  if (has(t, PANEL_CLOSE)) return { type: "panel", open: false };
  if (has(t, PANEL)) return { type: "panel", open: true };
  if (has(t, MINI)) return { type: "mini" };
  if (has(t, SCREEN)) return { type: "vision", source: "screen", question: text };
  if (has(t, CAMERA)) return { type: "vision", source: "camera", question: text };
  return { type: "chat", text };
}

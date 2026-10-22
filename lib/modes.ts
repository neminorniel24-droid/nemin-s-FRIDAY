// Turns what you said into an intent. Edit the phrase lists to change the words she reacts to.

export const WAKE_RE = /\b(nemiii+|nemi+|nemy|nemmy|nemmi|nammy|nami)\b/i;

const VIDEO = ["come here", "show yourself", "anime mode", "show anime", "show video", "video mode"];
const ORB = ["back to orb", "go back to orb", "show orb", "orb mode", "hide video", "hide anime", "go back"];
const STOP = ["stop", "be quiet", "quiet", "shut up", "stop talking", "that's enough", "enough"];
const CAMERA = ["what do you see", "what can you see", "look at me", "look at this", "what am i holding",
  "what is this", "what's this", "see this", "look at the camera", "use the camera"];
const SCREEN = ["look at my screen", "what's on my screen", "what is on my screen", "read my screen",
  "see my screen", "look at the screen", "what am i looking at", "explain my screen"];

export type Intent =
  | { type: "mode"; mode: "orb" | "video" }
  | { type: "stop" }
  | { type: "vision"; source: "camera" | "screen"; question: string }
  | { type: "chat"; text: string };

export function norm(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9' ]+/g, " ").replace(/\s+/g, " ").trim();
}

/** Remove "hey nemiii," style wake words from the front of a sentence. */
export function stripWake(s: string): string {
  return s.replace(/^\s*(hey|hi|hello|ok|okay)?[\s,]*(nemiii+|nemi+|nemy|nemmy|nemmi|nammy|nami)\b[\s,.!?:-]*/i, "").trim();
}

const has = (t: string, list: string[]) => list.some((p) => t.includes(p));

export function classify(raw: string): Intent {
  const text = stripWake(raw);
  const t = norm(text);
  if (has(t, ORB)) return { type: "mode", mode: "orb" };
  if (has(t, VIDEO)) return { type: "mode", mode: "video" };
  if (t.length < 22 && STOP.some((p) => t === p || t.startsWith(p + " "))) return { type: "stop" };
  if (has(t, SCREEN)) return { type: "vision", source: "screen", question: text };
  if (has(t, CAMERA)) return { type: "vision", source: "camera", question: text };
  return { type: "chat", text };
}

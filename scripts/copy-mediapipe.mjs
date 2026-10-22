// Copies the hand-tracking engine (wasm) into public/ so it loads locally, no CDN needed.
import { cpSync, existsSync, mkdirSync } from "node:fs";
const from = "node_modules/@mediapipe/tasks-vision/wasm";
const to = "public/mediapipe/wasm";
if (existsSync(from)) {
  mkdirSync(to, { recursive: true });
  cpSync(from, to, { recursive: true });
  console.log("hand-tracking engine copied to", to);
}

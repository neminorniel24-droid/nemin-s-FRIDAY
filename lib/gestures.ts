// Hand gestures through the webcam (MediaPipe, runs fully in your browser).
//
//   double pinch (thumb + index, twice)  -> "double_pinch"   greet / wake
//   open hand swiping left or right      -> "swipe_left" / "swipe_right"   switch tab
//   closed fist, held ~1 second          -> "fist"            minimise everything
//   two fingers up, held                 -> "two_fingers"     copy
//   three fingers up, held               -> "three_fingers"   paste
//
// Left/right are from YOUR point of view.

import { FilesetResolver, HandLandmarker } from "@mediapipe/tasks-vision";

export type GestureName = "double_pinch" | "swipe_left" | "swipe_right" | "fist" | "two_fingers" | "three_fingers";

const MODEL_LOCAL = "/mediapipe/hand_landmarker.task";
const MODEL_REMOTE =
  "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";

const HOLD_MS = 900;
const COOLDOWN_MS = 1400;
const DETECT_EVERY_MS = 40;
const SWIPE_DIST = 0.25; // fraction of the picture width
const SWIPE_WINDOW_MS = 450;
const DOUBLE_PINCH_MS = 1000;

type Pt = { x: number; y: number; z: number };
const dist = (a: Pt, b: Pt) => Math.hypot(a.x - b.x, a.y - b.y);

/** A finger counts as "up" when its tip is farther from the wrist than its middle joint. */
function fingersUp(lm: Pt[]): { index: boolean; middle: boolean; ring: boolean; pinky: boolean } {
  const up = (tip: number, pip: number) => dist(lm[tip], lm[0]) > dist(lm[pip], lm[0]) * 1.12;
  return { index: up(8, 6), middle: up(12, 10), ring: up(16, 14), pinky: up(20, 18) };
}

export class HandGestures {
  private landmarker: HandLandmarker | null = null;
  private stream: MediaStream | null = null;
  private raf = 0;
  private running = false;
  private lastVideoTime = -1;

  private wristTrail: { t: number; x: number }[] = [];
  private pinching = false;
  private pinchTimes: number[] = [];
  private holdPose: string | null = null;
  private holdSince = 0;
  private holdFired = false;
  private cooldownUntil = 0;
  private lastDetect = 0;

  constructor(private onGesture: (g: GestureName) => void, private onStatus?: (s: string) => void) {}

  get isRunning() {
    return this.running;
  }

  async start(video: HTMLVideoElement) {
    if (this.running) return;
    this.onStatus?.("loading hand tracking...");
    const fileset = await FilesetResolver.forVisionTasks("/mediapipe/wasm");
    let modelPath = MODEL_REMOTE;
    try {
      const head = await fetch(MODEL_LOCAL, { method: "HEAD" });
      if (head.ok && !/text\/html/.test(head.headers.get("content-type") || "")) modelPath = MODEL_LOCAL;
    } catch {
      /* use remote */
    }
    // GPU first (much lighter on the CPU), plain CPU if this PC can't do it
    const make = (delegate: "GPU" | "CPU") =>
      HandLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: modelPath, delegate },
        runningMode: "VIDEO",
        numHands: 1,
      });
    try {
      this.landmarker = await make("GPU");
    } catch {
      this.landmarker = await make("CPU");
    }
    this.stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
    video.srcObject = this.stream;
    await video.play();
    this.running = true;
    this.onStatus?.("");
    const loop = () => {
      if (!this.running) return;
      this.tick(video);
      this.raf = requestAnimationFrame(loop);
    };
    loop();
  }

  stop() {
    this.running = false;
    cancelAnimationFrame(this.raf);
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.landmarker?.close();
    this.landmarker = null;
    this.wristTrail = [];
    this.pinching = false;
    this.holdPose = null;
  }

  private fire(g: GestureName, now: number) {
    if (now < this.cooldownUntil) return;
    this.cooldownUntil = now + COOLDOWN_MS;
    this.wristTrail = [];
    this.onGesture(g);
  }

  private tick(video: HTMLVideoElement) {
    if (!this.landmarker || video.readyState < 2 || video.currentTime === this.lastVideoTime) return;
    const now = performance.now();
    if (now - this.lastDetect < DETECT_EVERY_MS) return; // ~25 checks a second is plenty, keeps the PC cool
    this.lastDetect = now;
    this.lastVideoTime = video.currentTime;
    const res = this.landmarker.detectForVideo(video, now);
    const lm = res.landmarks?.[0] as Pt[] | undefined;
    if (!lm) {
      this.wristTrail = [];
      this.holdPose = null;
      this.pinching = false;
      return;
    }

    // ---- pinch / double pinch
    const handSize = dist(lm[0], lm[9]) || 0.1;
    const pinchNow = dist(lm[4], lm[8]) < handSize * 0.28;
    if (pinchNow && !this.pinching) {
      this.pinchTimes = this.pinchTimes.filter((t) => now - t < DOUBLE_PINCH_MS);
      this.pinchTimes.push(now);
      if (this.pinchTimes.length >= 2) {
        this.pinchTimes = [];
        this.fire("double_pinch", now);
      }
    }
    this.pinching = pinchNow;

    // ---- pose
    const f = fingersUp(lm);
    const count = [f.index, f.middle, f.ring, f.pinky].filter(Boolean).length;
    let pose: string | null = null;
    if (pinchNow) pose = null;
    else if (count === 0) pose = "fist";
    else if (f.index && f.middle && !f.ring && !f.pinky) pose = "two_fingers";
    else if (f.index && f.middle && f.ring && !f.pinky) pose = "three_fingers";
    else if (count === 4) pose = "open";

    // ---- swipe (open hand moving sideways)
    if (pose === "open") {
      this.wristTrail.push({ t: now, x: lm[0].x });
      this.wristTrail = this.wristTrail.filter((p) => now - p.t < SWIPE_WINDOW_MS);
      const first = this.wristTrail[0];
      if (first && now - first.t > 150) {
        const dx = lm[0].x - first.x; // camera image is not mirrored: your right = smaller x
        if (dx < -SWIPE_DIST) this.fire("swipe_right", now);
        else if (dx > SWIPE_DIST) this.fire("swipe_left", now);
      }
    } else this.wristTrail = [];

    // ---- hold poses
    if (pose === "fist" || pose === "two_fingers" || pose === "three_fingers") {
      if (this.holdPose !== pose) {
        this.holdPose = pose;
        this.holdSince = now;
        this.holdFired = false;
      } else if (!this.holdFired && now - this.holdSince > HOLD_MS) {
        this.holdFired = true;
        this.fire(pose, now);
      }
    } else {
      this.holdPose = null;
    }
  }
}

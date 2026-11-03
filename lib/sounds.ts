// Tiny interface sounds made with the browser's audio engine (no files). Mute with the SOUND button.
let ctx: AudioContext | null = null;
let muted = false;

try {
  muted = localStorage.getItem("nemiii.muted") === "1";
} catch {
  /* ignore */
}

export const sounds = {
  get muted() {
    return muted;
  },
  setMuted(m: boolean) {
    muted = m;
    try {
      localStorage.setItem("nemiii.muted", m ? "1" : "0");
    } catch {
      /* ignore */
    }
  },
  /** Call once from a click so the browser allows sound. */
  prime() {
    try {
      ctx = ctx || new AudioContext();
      void ctx.resume();
    } catch {
      /* ignore */
    }
  },
  tone(freq: number, start: number, len: number, vol = 0.05, type: OscillatorType = "sine") {
    if (muted || !ctx) return;
    const t0 = ctx.currentTime + start;
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = type;
    o.frequency.value = freq;
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(vol, t0 + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + len);
    o.connect(g).connect(ctx.destination);
    o.start(t0);
    o.stop(t0 + len + 0.05);
  },
  startup() {
    [392, 523, 784].forEach((f, i) => this.tone(f, i * 0.11, 0.35, 0.05));
  },
  listenOn() {
    this.tone(660, 0, 0.12, 0.035);
  },
  listenOff() {
    this.tone(440, 0, 0.12, 0.03);
  },
  ask() {
    this.tone(520, 0, 0.1, 0.04);
    this.tone(520, 0.16, 0.1, 0.04);
  },
  alert() {
    for (let i = 0; i < 3; i++) this.tone(880, i * 0.22, 0.14, 0.06, "triangle");
  },
};

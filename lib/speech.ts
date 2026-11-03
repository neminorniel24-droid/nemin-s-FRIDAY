// Browser speech: Speaker (text -> voice) and Listener (voice -> text).
// Both use the free built-in Web Speech API in Chrome / Edge.

/* eslint-disable @typescript-eslint/no-explicit-any */
import { BACKEND } from "./api";
import { cleanForSpeech } from "./speechText";

// ------------------------------------------------------------------ Speaker
const PREFERRED = [
  /natural.*(aria|jenny|sonia|neerja|swara)/i, // Edge's very natural voices
  /google uk english female/i,
  /(aria|jenny|sonia|neerja|swara|zira|samantha|heera)/i,
  /female/i,
];

export function pickVoice(
  voices: SpeechSynthesisVoice[],
  saved?: string | null,
  prefer?: string | null,
): SpeechSynthesisVoice | null {
  if (saved) {
    const s = voices.find((v) => v.name === saved);
    if (s) return s;
  }
  const english = voices.filter((v) => /^en/i.test(v.lang));
  if (prefer) {
    // "Auto voice": each mode (Jarvis, Friday, Edith) tries to pick a voice that suits it.
    try {
      const re = new RegExp(prefer, "i");
      const hit = english.find((v) => re.test(v.name));
      if (hit) return hit;
    } catch {
      /* bad pattern: fall through */
    }
  }
  for (const re of PREFERRED) {
    const hit = english.find((v) => re.test(v.name));
    if (hit) return hit;
  }
  return english[0] || voices[0] || null;
}

/** Split a reply into short pieces. Chrome cuts off long utterances, short ones are safe. */
export function chunk(text: string, max = 170): string[] {
  const sentences = text.replace(/\s+/g, " ").trim().split(/(?<=[.!?])\s+/);
  const out: string[] = [];
  for (const s of sentences) {
    if (s.length <= max) {
      if (s) out.push(s);
      continue;
    }
    let cur = "";
    for (const part of s.split(/(?<=,)\s+/)) {
      if ((cur + " " + part).length > max && cur) {
        out.push(cur.trim());
        cur = part;
      } else cur += " " + part;
    }
    if (cur.trim()) out.push(cur.trim());
  }
  return out;
}

export class Speaker {
  voiceName: string | null = null;
  rate = 0.95; // 1 = normal. Slightly slower sounds calmer. Set per mode.
  pitch = 1.05;
  prefer: string | null = null; // regex of voice names to prefer in "Auto voice"
  natural = false; // true = use the offline Kokoro voice from the backend (falls back to the browser voice on any problem)
  speaking = false;
  paused = false;
  /** Called when the natural voice failed and the browser voice took over. */
  onNaturalFail?: () => void;
  private token = 0;
  private audio: HTMLAudioElement | null = null;
  private abort: AbortController | null = null;
  private rearm: (() => void) | null = null;
  private disarm: (() => void) | null = null;

  voices(): SpeechSynthesisVoice[] {
    return typeof speechSynthesis === "undefined" ? [] : speechSynthesis.getVoices();
  }

  /** Must be called from a click once, so the browser allows speech afterwards. */
  prime() {
    try {
      const u = new SpeechSynthesisUtterance(" ");
      u.volume = 0;
      speechSynthesis.speak(u);
    } catch {
      /* ignore */
    }
  }

  /** Pause in the middle of a sentence. resume() carries on from the same spot. */
  pause() {
    if (!this.speaking || this.paused) return;
    this.paused = true;
    this.disarm?.();
    try {
      this.audio?.pause();
      speechSynthesis.pause();
    } catch {
      /* ignore */
    }
  }

  resume() {
    if (!this.paused) return;
    this.paused = false;
    try {
      void this.audio?.play();
      speechSynthesis.resume();
    } catch {
      /* ignore */
    }
    this.rearm?.();
  }

  cancel() {
    this.token++;
    this.paused = false;
    this.abort?.abort();
    this.abort = null;
    try {
      this.audio?.pause();
    } catch {
      /* ignore */
    }
    this.audio = null;
    try {
      speechSynthesis.cancel();
    } catch {
      /* ignore */
    }
  }

  /** Resolves true when finished, false if it was cancelled or the browser blocked it. */
  async speak(text: string, onStart?: () => void): Promise<boolean> {
    this.cancel();
    const my = this.token;
    const clean = cleanForSpeech(text);
    if (!clean) return true;
    this.speaking = true;
    let started = false;
    const markStart = () => {
      if (!started) {
        started = true;
        onStart?.();
      }
    };
    try {
      if (this.natural) {
        const pieces = chunk(clean, 240);
        const done = await this.speakNatural(pieces, my, markStart);
        if (done === "cancelled") return false;
        if (done === "finished") return my === this.token;
        // the natural voice broke: carry on in the browser voice from where it stopped
        this.onNaturalFail?.();
        return await this.speakBrowser(chunk(clean, 170).slice(done), my, markStart);
      }
      return await this.speakBrowser(chunk(clean), my, markStart);
    } finally {
      if (my === this.token) {
        this.speaking = false;
        this.paused = false;
      }
    }
  }

  // ---- natural voice: the backend turns each sentence into audio while the previous one plays
  private async fetchWav(piece: string, signal: AbortSignal): Promise<Blob | null> {
    try {
      const r = await fetch(BACKEND + "/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: piece }),
        signal,
      });
      return r.ok ? await r.blob() : null;
    } catch {
      return null;
    }
  }

  /** Returns "finished", "cancelled", or the number of pieces already spoken when it failed. */
  private async speakNatural(pieces: string[], my: number, markStart: () => void): Promise<"finished" | "cancelled" | number> {
    const ctrl = new AbortController();
    this.abort = ctrl;
    let next: Promise<Blob | null> = this.fetchWav(pieces[0], ctrl.signal);
    for (let i = 0; i < pieces.length; i++) {
      const blob = await next;
      if (my !== this.token) return "cancelled";
      if (!blob) return i;
      next = i + 1 < pieces.length ? this.fetchWav(pieces[i + 1], ctrl.signal) : Promise.resolve(null);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      this.audio = audio;
      const ok = await new Promise<boolean>((resolve) => {
        audio.onplaying = markStart;
        audio.onended = () => resolve(true);
        audio.onerror = () => resolve(false);
        audio.play().catch(() => resolve(false));
      });
      URL.revokeObjectURL(url);
      if (my !== this.token) return "cancelled";
      if (!ok) return i;
    }
    return "finished";
  }

  // ---- browser voice
  private async speakBrowser(pieces: string[], my: number, markStart: () => void): Promise<boolean> {
    if (!pieces.length) return true;
    const voice = pickVoice(this.voices(), this.voiceName, this.prefer);
    for (const piece of pieces) {
      if (my !== this.token) return false;
      const ok = await new Promise<boolean>((resolve) => {
        const u = new SpeechSynthesisUtterance(piece);
        if (voice) u.voice = voice;
        u.lang = voice?.lang || "en-US";
        u.rate = this.rate;
        u.pitch = this.pitch;
        u.onstart = markStart;
        // Safety net: if the browser never reports the end (no voice installed), do not hang forever.
        // It is switched off while paused, so a pause can be as long as you like.
        let guard: ReturnType<typeof setTimeout> | null = null;
        const arm = () => {
          if (guard) clearTimeout(guard);
          guard = setTimeout(() => resolve(true), 4000 + piece.length * 110);
        };
        const stop = () => {
          if (guard) clearTimeout(guard);
          guard = null;
        };
        this.rearm = arm;
        this.disarm = stop;
        arm();
        u.onend = () => { stop(); resolve(true); };
        u.onerror = (e: SpeechSynthesisErrorEvent) => {
          stop();
          resolve(e.error === "interrupted" || e.error === "canceled");
        };
        speechSynthesis.speak(u);
      });
      this.rearm = this.disarm = null;
      if (!ok) return false;
    }
    return my === this.token;
  }
}

// ----------------------------------------------------------------- Listener
interface ListenerCallbacks {
  onFinal: (text: string) => void;
  onInterim?: (text: string) => void;
  onActive?: (on: boolean) => void;
  onError?: (message: string) => void;
}

export class Listener {
  private rec: any = null;
  private wanted = false;
  private paused = false;
  private continuous = false;
  lang = "en-IN"; // Indian English understands your accent best; change if you like

  constructor(private cb: ListenerCallbacks) {}

  static supported(): boolean {
    return typeof window !== "undefined" && !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
  }

  get active(): boolean {
    return this.wanted;
  }

  start(continuous: boolean) {
    this.wanted = true;
    this.paused = false;
    this.continuous = continuous;
    this.spawn();
  }

  stop() {
    this.wanted = false;
    this.paused = false;
    this.kill();
    this.cb.onActive?.(false);
  }

  /** Stop hearing for a moment (so she does not hear herself). */
  pause() {
    this.paused = true;
    this.kill();
  }

  resume() {
    this.paused = false;
    if (this.wanted) this.spawn();
  }

  private kill() {
    const r = this.rec;
    this.rec = null;
    if (r) {
      r.onend = r.onresult = r.onerror = null;
      try {
        r.abort();
      } catch {
        /* ignore */
      }
    }
  }

  private spawn() {
    if (this.rec || this.paused || !this.wanted) return;
    const Ctor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!Ctor) {
      this.cb.onError?.("This browser has no speech recognition. Use Chrome or Edge.");
      this.wanted = false;
      return;
    }
    const rec = new Ctor();
    rec.lang = this.lang;
    rec.continuous = this.continuous;
    rec.interimResults = true;
    let gotResult = false;

    rec.onstart = () => this.cb.onActive?.(true);
    rec.onresult = (e: any) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        const text: string = res[0].transcript;
        if (res.isFinal) {
          gotResult = true;
          this.cb.onInterim?.("");
          if (text.trim()) this.cb.onFinal(text.trim());
        } else interim += text;
      }
      if (interim) this.cb.onInterim?.(interim);
    };
    rec.onerror = (e: any) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        this.wanted = false;
        this.cb.onError?.("Microphone is blocked. Click the lock icon in the address bar and allow the microphone.");
      } else if (e.error === "network") {
        this.cb.onError?.("Speech recognition needs internet (Chrome sends audio to Google). Check your connection.");
      } else if (e.error === "audio-capture") {
        this.wanted = false;
        this.cb.onError?.("I can't find a microphone.");
      }
      // "no-speech" and "aborted" are normal, ignore
    };
    rec.onend = () => {
      this.rec = null;
      if (this.wanted && !this.paused && (this.continuous || false)) {
        setTimeout(() => this.spawn(), 250);
      } else if (!this.continuous && !this.paused) {
        this.wanted = false;
        this.cb.onInterim?.("");
        this.cb.onActive?.(false);
      }
      void gotResult;
    };
    this.rec = rec;
    try {
      rec.start();
    } catch {
      this.rec = null;
    }
  }
}

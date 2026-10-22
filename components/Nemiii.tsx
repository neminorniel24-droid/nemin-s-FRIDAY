"use client";
// The whole Nemiii screen: wires voice, orb / video, gestures, vision and the backend together.
//
// Reading guide:
//   1. state + refs
//   2. say()            makes her speak (and pauses the microphone while she does)
//   3. handleUtterance  decides what to do with something you said
//   4. gestures, buttons, keyboard
//   5. the screen (JSX)

import { useCallback, useEffect, useRef, useState } from "react";
import Dashboard, { useLocation } from "./Dashboard";
import OrbCanvas from "./OrbCanvas";
import VideoStage from "./VideoStage";
import { api } from "@/lib/api";
import { HandGestures, type GestureName } from "@/lib/gestures";
import { WAKE_RE, classify, stripWake } from "@/lib/modes";
import { Listener, Speaker } from "@/lib/speech";
import type { AvatarState, Health, Mode } from "@/lib/types";
import { captureCamera, captureScreen } from "@/lib/vision";

const AWAKE_MS = 45_000; // after you speak to her, she keeps listening this long without the wake word

const GESTURE_LABEL: Record<GestureName, string> = {
  double_pinch: "Hello",
  swipe_left: "Previous tab",
  swipe_right: "Next tab",
  fist: "Minimise all",
  two_fingers: "Copy",
  three_fingers: "Paste",
};

export default function Nemiii() {
  // ------------------------------------------------------------ 1. state
  const [started, setStarted] = useState(false);
  const [mode, setMode] = useState<Mode>("orb");
  const [phase, setPhase] = useState<"idle" | "thinking" | "speaking">("idle");
  const [micOn, setMicOn] = useState(false);
  const [wakeOn, setWakeOn] = useState(false);
  const [gesturesOn, setGesturesOn] = useState(false);
  const [caption, setCaption] = useState("");
  const [heard, setHeard] = useState("");
  const [toast, setToast] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const [online, setOnline] = useState(true);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [voiceName, setVoiceName] = useState("");
  const coords = useLocation();

  const speaker = useRef(new Speaker());
  const listener = useRef<Listener | null>(null);
  const gestures = useRef<HandGestures | null>(null);
  const camVideo = useRef<HTMLVideoElement>(null);
  const awakeUntil = useRef(0);
  const busy = useRef(false);
  const captionTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingScreenQuestion = useRef("");
  const coordsRef = useRef(coords);
  coordsRef.current = coords;
  const nameRef = useRef("boss");
  nameRef.current = health?.user_name || "boss";

  const avatar: AvatarState = phase !== "idle" ? phase : micOn ? "listening" : "idle";

  const flash = useCallback((msg: string, ms = 3500) => {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), ms);
  }, []);

  // ------------------------------------------------------------- 2. say
  const say = useCallback(async (text: string): Promise<boolean> => {
    if (!text) return true;
    if (captionTimer.current) clearTimeout(captionTimer.current);
    setCaption(text);
    setPhase("speaking");
    listener.current?.pause(); // do not listen to herself
    const ok = await speaker.current.speak(text);
    setPhase("idle");
    listener.current?.resume();
    captionTimer.current = setTimeout(() => setCaption(""), 5000);
    return ok;
  }, []);

  // ---------------------------------------------------- 3. handleUtterance
  const handleUtterance = useCallback(
    async (raw: string, force = false) => {
      const text = raw.trim();
      if (!text || busy.current) return;
      const now = Date.now();
      if (!force && now > awakeUntil.current && !WAKE_RE.test(text)) return; // background chatter
      awakeUntil.current = now + AWAKE_MS;

      const intent = classify(text);
      busy.current = true;
      try {
        if (intent.type === "stop") {
          speaker.current.cancel();
          setPhase("idle");
          setCaption("");
        } else if (intent.type === "mode") {
          setMode(intent.mode);
          await say(intent.mode === "video" ? "I'm here." : "Back to the orb.");
        } else if (intent.type === "vision") {
          if (intent.source === "screen") {
            // Browsers only allow screen sharing after a real click, so voice cannot start it.
            pendingScreenQuestion.current = intent.question;
            await say("Press the Screen button and choose what I should look at.");
          } else {
            setPhase("thinking");
            try {
              const img = await captureCamera(camVideo.current);
              const r = await api.vision(img, intent.question);
              await say(r.reply);
              if (r.error) flash(r.error, 8000);
            } catch {
              await say("I couldn't use the camera. Please allow camera access.");
            }
          }
        } else if (!stripWake(text)) {
          await say("Yes, I'm here.");
        } else {
          setPhase("thinking");
          setCaption("");
          try {
            const r = await api.chat(intent.text, coordsRef.current?.lat, coordsRef.current?.lon);
            setOnline(true);
            await say(r.reply);
            if (r.error) flash(r.error, 9000);
          } catch {
            setOnline(false);
            await say("I can't reach my backend. Please check that it is running.");
          }
        }
      } finally {
        busy.current = false;
        setPhase((p) => (p === "thinking" ? "idle" : p));
      }
    },
    [say, flash],
  );

  // ------------------------------------------------- microphone plumbing
  useEffect(() => {
    listener.current = new Listener({
      onFinal: (t) => {
        setHeard("");
        handleUtteranceRef.current(t, oneShot.current);
      },
      onInterim: (t) => setHeard(t),
      onActive: (on) => setMicOn(on),
      onError: (m) => flash(m, 9000),
    });
    return () => listener.current?.stop();
  }, [flash]);

  const handleUtteranceRef = useRef(handleUtterance);
  handleUtteranceRef.current = handleUtterance;
  const oneShot = useRef(false);

  const startWake = useCallback(() => {
    oneShot.current = false;
    listener.current?.start(true);
    setWakeOn(true);
  }, []);

  const stopWake = useCallback(() => {
    listener.current?.stop();
    setWakeOn(false);
  }, []);

  const talkOnce = useCallback(() => {
    if (wakeOn) {
      awakeUntil.current = Date.now() + AWAKE_MS; // already listening: just skip the wake word
      flash("Listening. Just speak.");
      return;
    }
    oneShot.current = true;
    listener.current?.start(false);
  }, [wakeOn, flash]);

  // ---------------------------------------------------------- 4. gestures
  const toggleGestures = useCallback(async () => {
    if (gesturesOn) {
      gestures.current?.stop();
      setGesturesOn(false);
      return;
    }
    const g = new HandGestures(
      (name) => {
        flash(GESTURE_LABEL[name], 1800);
        if (name === "double_pinch") {
          awakeUntil.current = Date.now() + AWAKE_MS;
          if (!listener.current?.active) startWake();
          void say(`Hello ${nameRef.current}. I'm listening.`);
        } else {
          api.gesture(name).catch(() => flash("Gesture failed: backend offline", 3000));
        }
      },
      (s) => s && flash(s, 6000),
    );
    gestures.current = g;
    try {
      if (!camVideo.current) return;
      await g.start(camVideo.current);
      setGesturesOn(true);
      flash("Gestures on. Double pinch to greet, swipe for tabs, fist to minimise.", 6000);
    } catch (e) {
      g.stop();
      flash("Couldn't start hand tracking: " + (e instanceof Error ? e.message : "camera blocked"), 9000);
    }
  }, [gesturesOn, flash, say, startWake]);

  const lookCamera = useCallback(() => void handleUtterance("what do you see", true), [handleUtterance]);

  const lookScreen = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    setPhase("thinking");
    try {
      const img = await captureScreen();
      const q = pendingScreenQuestion.current || "Describe what is on this screen and help me with it.";
      pendingScreenQuestion.current = "";
      const r = await api.vision(img, q);
      await say(r.reply);
    } catch {
      await say("I couldn't capture the screen.");
    } finally {
      busy.current = false;
      setPhase((p) => (p === "thinking" ? "idle" : p));
    }
  }, [say]);

  const clearMemory = useCallback(async () => {
    try {
      await api.resetMemory(false);
      flash("Conversation cleared. Saved facts are kept.");
    } catch {
      flash("Backend offline");
    }
  }, [flash]);

  // ----------------------------------------------------- voices + health
  useEffect(() => {
    const load = () => {
      const v = speechSynthesis.getVoices().filter((x) => /^en/i.test(x.lang));
      setVoices(v);
    };
    load();
    speechSynthesis.addEventListener("voiceschanged", load);
    try {
      const saved = localStorage.getItem("nemiii.voice");
      if (saved) {
        setVoiceName(saved);
        speaker.current.voiceName = saved;
      }
    } catch {
      /* private mode */
    }
    return () => speechSynthesis.removeEventListener("voiceschanged", load);
  }, []);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const h = await api.health();
        if (alive) {
          setHealth(h);
          setOnline(true);
        }
      } catch {
        if (alive) setOnline(false);
      }
    };
    poll();
    const id = setInterval(poll, 20_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // ------------------------------------------------------------- start up
  const begin = useCallback(
    async (auto = false) => {
      speaker.current.prime();
      setStarted(true);
      awakeUntil.current = Date.now() + AWAKE_MS;
      const ok = await say(`Hello ${nameRef.current}. Systems online. What are we working on today?`);
      if (!ok && auto) {
        setStarted(false); // the browser blocked speech: ask for one click instead
        return;
      }
      if (Listener.supported()) startWake();
      else flash("Voice input needs Chrome or Edge.", 9000);
    },
    [say, startWake, flash],
  );

  useEffect(() => {
    if (health && new URLSearchParams(window.location.search).get("auto") === "1") void begin(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [health === null]);

  // -------------------------------------------------------------- keyboard
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || e.ctrlKey || e.metaKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (!started) return;
      if (k === "v") talkOnce();
      else if (k === "w") (wakeOn ? stopWake : startWake)();
      else if (k === "g") void toggleGestures();
      else if (k === "m") setMode((m) => (m === "orb" ? "video" : "orb"));
      else if (k === "c") lookCamera();
      else if (k === "s") void lookScreen();
      else if (k === " " || k === "escape") {
        speaker.current.cancel();
        setPhase("idle");
        if (k === " ") e.preventDefault();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [started, wakeOn, talkOnce, startWake, stopWake, toggleGestures, lookCamera, lookScreen]);

  // ---------------------------------------------------------- 5. the screen
  const brain = !health
    ? "CONNECTING"
    : health.local.ready
      ? `LOCAL · ${health.local.model}`
      : health.groq_configured
        ? "CLOUD · GROQ"
        : "NO BRAIN: see README";

  return (
    <main className="stage">
      {mode === "orb" ? <OrbCanvas state={avatar} /> : <VideoStage state={avatar} />}

      <div className="hud">
        <div className="title">
          <div className="name">N · E · M · I · I · I</div>
          <div className="sub">VOICE-CONTROLLED PC ASSISTANT</div>
          <div className="sub">
            BRAIN: {brain} · MIC: {micOn ? "ON" : "OFF"} · PC: {health?.pc_control_available ? "LINKED" : "NOT LINKED"}
          </div>
        </div>

        <Dashboard coords={coords} online={online} />

        {!online && started && <div className="banner">Backend offline. Start it with ./run.sh</div>}
        {toast && <div className="toast">{toast}</div>}

        <div className="bottom">
          {heard && <div className="heard">{heard}</div>}
          {caption && <div className="caption">{caption}</div>}
        </div>

        <div className="controls">
          <button onClick={talkOnce}>TALK <kbd>V</kbd></button>
          <button className={wakeOn ? "on" : ""} onClick={wakeOn ? stopWake : startWake}>
            WAKE WORD {wakeOn ? "ON" : "OFF"} <kbd>W</kbd>
          </button>
          <button className={gesturesOn ? "on" : ""} onClick={() => void toggleGestures()}>
            GESTURES {gesturesOn ? "ON" : "OFF"} <kbd>G</kbd>
          </button>
          <button onClick={() => setMode(mode === "orb" ? "video" : "orb")}>
            {mode === "orb" ? "COME HERE" : "BACK TO ORB"} <kbd>M</kbd>
          </button>
          <button onClick={lookCamera}>LOOK <kbd>C</kbd></button>
          <button onClick={() => void lookScreen()}>SCREEN <kbd>S</kbd></button>
          <select
            value={voiceName}
            onChange={(e) => {
              setVoiceName(e.target.value);
              speaker.current.voiceName = e.target.value;
              try {
                localStorage.setItem("nemiii.voice", e.target.value);
              } catch {
                /* ignore */
              }
              void say("This is my voice.");
            }}
          >
            <option value="">Auto voice</option>
            {voices.map((v) => (
              <option key={v.name} value={v.name}>{v.name}</option>
            ))}
          </select>
          <button className="small" onClick={() => void clearMemory()}>CLEAR CHAT</button>
        </div>

        <div className="hints">
          SAY “NEMIII, …” · “COME HERE” · “BACK TO ORB” · “WHAT DO YOU SEE” · SPACE = STOP TALKING
        </div>
      </div>

      {/* hidden camera used for hand gestures and "what do you see" */}
      <video ref={camVideo} className="cam-hidden" muted playsInline />

      {!started && (
        <button className="wake" onClick={() => void begin(false)}>
          <span>TAP TO WAKE NEMIII</span>
          <small>one click lets the browser use the speaker and microphone</small>
        </button>
      )}
    </main>
  );
}

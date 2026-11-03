"use client";
// The whole Nemiii screen: wires voice, typing, orb / video, gestures, vision and the backend together.
//
// Reading guide:
//   1. state + refs
//   2. say()            makes her speak (and pauses the microphone while she does)
//   3. handleUtterance  decides what to do with something you said or typed
//   4. gestures, reminders, buttons, keyboard
//   5. the screen (JSX)

import { useCallback, useEffect, useRef, useState } from "react";
import ChatBar from "./ChatBar";
import Creations from "./Creations";
import Dashboard, { useLocation } from "./Dashboard";
import Drawer, { type Tab } from "./Drawer";
import OrbCanvas from "./OrbCanvas";
import VideoStage from "./VideoStage";
import { api } from "@/lib/api";
import { MicLevel } from "@/lib/audioLevel";
import { HandGestures, type GestureName } from "@/lib/gestures";
import { WAKE_RE, calledPersona, classify, stripWake } from "@/lib/modes";
import { sounds } from "@/lib/sounds";
import { cleanForDisplay } from "@/lib/speechText";
import { Listener, Speaker } from "@/lib/speech";
import { THEMES, THEME_ORDER, applyTheme, isTheme, type ThemeKey } from "@/lib/themes";
import type { AvatarState, ChatLine, ChatResponse, Health, Mode, PersonaInfo } from "@/lib/types";
import { captureCamera, captureScreen } from "@/lib/vision";

const AWAKE_MS = 45_000; // after you speak to her, she keeps listening this long without the wake word
const REMINDER_POLL_MS = 6_000;
const STUDIO_MAKERS = new Set(["generate_image", "make_music", "make_speech", "transcribe_audio"]);

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
  const [theme, setThemeState] = useState<ThemeKey>("peacock");
  const [persona, setPersona] = useState<PersonaInfo | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("chat");
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [muted, setMuted] = useState(sounds.muted);
  const [voiceReplies, setVoiceReplies] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [making, setMaking] = useState(false);
  const [speakPaused, setSpeakPaused] = useState(false);
  const [naturalPref, setNaturalPref] = useState(true);
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
  const lineId = useRef(0);
  const chan = useRef<BroadcastChannel | null>(null);
  const micLevel = useRef<MicLevel | null>(null);
  if (!micLevel.current) micLevel.current = new MicLevel();
  const getLevel = useCallback(() => micLevel.current!.read(), []);

  const coordsRef = useRef(coords);
  coordsRef.current = coords;
  const addressRef = useRef("boss");
  addressRef.current = health?.address_as || "boss";
  const voiceRepliesRef = useRef(voiceReplies);
  voiceRepliesRef.current = voiceReplies;
  const phaseRef = useRef(phase);
  phaseRef.current = phase;

  const avatar: AvatarState = phase !== "idle" ? phase : micOn ? "listening" : "idle";
  const avatarRef = useRef(avatar);
  avatarRef.current = avatar;
  const themeRef = useRef(theme);
  themeRef.current = theme;

  const flash = useCallback((msg: string, ms = 3500) => {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), ms);
  }, []);

  const addLine = useCallback((role: ChatLine["role"], text: string) => {
    if (!text) return;
    setLines((ls) => [...ls.slice(-79), { id: ++lineId.current, role, text, at: Date.now() }]);
  }, []);

  // Her personality changes how she sounds (speed, pitch, preferred voice). Applied right away.
  const applyPersona = useCallback((p: PersonaInfo) => {
    speaker.current.rate = p.rate;
    speaker.current.pitch = p.pitch;
    speaker.current.prefer = p.prefer_voice;
    setPersona(p);
  }, []);

  const changeTheme = useCallback((t: ThemeKey, tellServer = true) => {
    setThemeState(t);
    if (tellServer) api.setTheme(t).catch(() => {});
  }, []);

  // ------------------------------------------------------------- 2. say
  const say = useCallback(async (text: string): Promise<boolean> => {
    if (!text) return true;
    const shown = cleanForDisplay(text); // markdown marks are dropped on screen; the voice gets its own cleaner version
    addLine("her", shown);
    if (captionTimer.current) clearTimeout(captionTimer.current);
    setCaption(shown);
    setPhase("speaking");
    listener.current?.pause(); // do not listen to herself
    let ok = true;
    if (voiceRepliesRef.current) ok = await speaker.current.speak(text);
    else await new Promise((r) => setTimeout(r, Math.min(4000, 700 + text.length * 30))); // text-only: let it be read
    setSpeakPaused(false);
    setPhase("idle");
    listener.current?.resume();
    captionTimer.current = setTimeout(() => setCaption(""), 5000);
    return ok;
  }, [addLine]);

  // What the backend said can also change the screen (theme) and her mode.
  const applyReply = useCallback((r: ChatResponse) => {
    const p = r.ui?.persona || r.persona;
    if (p) applyPersona(p);
    const t = r.ui?.theme;
    if (t && isTheme(t)) changeTheme(t, false);
    setConfirming(!!r.confirm);
    if (r.confirm) sounds.ask();
    if (r.ui?.gallery) setViewerOpen(true);
    if (r.actions?.some((a) => STUDIO_MAKERS.has(a.name) && a.ok)) setMaking(true); // show the progress bar
  }, [applyPersona, changeTheme]);

  // Pause / resume the voice in the middle of a long answer. STOP cuts it off.
  const togglePause = useCallback(() => {
    const sp = speaker.current;
    if (!sp.speaking) return;
    if (sp.paused) sp.resume();
    else sp.pause();
    setSpeakPaused(sp.paused);
  }, []);

  const stopTalking = useCallback(() => {
    speaker.current.cancel();
    setSpeakPaused(false);
    setPhase("idle");
    setCaption("");
  }, []);

  const openMini = useCallback(() => {
    const w = window.open(`${window.location.origin}/mini`, "nemiii-mini", "popup=yes,width=300,height=300,left=40,top=60");
    if (!w) flash("The browser blocked the mini window. Allow pop-ups for this page.", 6000);
    else flash("Mini orb open. Press Win+Ctrl+T on it to keep it on top.", 6000);
  }, [flash]);

  // ---------------------------------------------------- 3. handleUtterance
  const handleUtterance = useCallback(
    async (raw: string, force = false) => {
      const text = raw.trim();
      if (!text || busy.current) return;
      const now = Date.now();
      if (!force && now > awakeUntil.current && !WAKE_RE.test(text)) return; // background chatter
      awakeUntil.current = now + AWAKE_MS;

      const intent = classify(text);
      const called = calledPersona(text);
      busy.current = true;
      try {
        if (intent.type === "stop") {
          stopTalking();
        } else if (intent.type === "gallery") {
          addLine("you", stripWake(text));
          setViewerOpen(intent.open);
          await say(intent.open ? "Here is what I made." : "Gallery closed.");
        } else if (intent.type === "mode") {
          addLine("you", stripWake(text));
          setMode(intent.mode);
          await say(intent.mode === "video" ? "I'm here." : "Back to the orb.");
        } else if (intent.type === "panel") {
          addLine("you", stripWake(text));
          setDrawerOpen(intent.open);
          await say(intent.open ? "Here is the panel." : "Panel closed.");
        } else if (intent.type === "mini") {
          addLine("you", stripWake(text));
          openMini();
          await say("Opening the mini orb.");
        } else if (intent.type === "vision") {
          addLine("you", stripWake(text));
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
          await say(called ? `${called[0].toUpperCase()}${called.slice(1)} here.` : "Yes, I'm here.");
        } else {
          addLine("you", intent.text);
          setPhase("thinking");
          setCaption("");
          try {
            const r = await api.chat(intent.text, coordsRef.current?.lat, coordsRef.current?.lon, called ?? undefined);
            setOnline(true);
            applyReply(r);
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
    [say, flash, addLine, applyReply, openMini, stopTalking],
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

  // The orb pulses with your voice while the microphone is on.
  useEffect(() => {
    if (micOn) void micLevel.current?.start();
    else micLevel.current?.stop();
  }, [micOn]);

  // Soft sounds when listening starts and stops.
  const firstMic = useRef(true);
  useEffect(() => {
    if (firstMic.current) {
      firstMic.current = false;
      return;
    }
    if (!started) return;
    if (micOn) sounds.listenOn();
    else sounds.listenOff();
  }, [micOn, started]);

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
          void say(`Hello ${addressRef.current}. I'm listening.`);
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
      setLines([]);
      flash("Conversation cleared. Saved facts are kept.");
    } catch {
      flash("Backend offline");
    }
  }, [flash]);

  // Typing instead of talking
  const sendTyped = useCallback(
    (text: string) => {
      if (busy.current) {
        flash("One moment, I'm still on the last one.");
        return;
      }
      if (!started) {
        speaker.current.prime();
        sounds.prime();
        setStarted(true);
      }
      void handleUtterance(text, true);
    },
    [started, handleUtterance, flash],
  );

  const cycleMode = useCallback(async () => {
    const list = health?.personas;
    if (!list?.length || !persona) return;
    const next = list[(list.findIndex((p) => p.key === persona.key) + 1) % list.length];
    try {
      const p = await api.setMode(next.key);
      applyPersona(p);
      void say(p.greeting);
    } catch {
      flash("Backend offline");
    }
  }, [health, persona, applyPersona, say, flash]);

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

  const firstHealth = useRef(true);
  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const h = await api.health();
        if (!alive) return;
        setHealth(h);
        setOnline(true);
        if (firstHealth.current) {
          firstHealth.current = false;
          applyPersona(h.persona);
          if (isTheme(h.theme)) setThemeState(h.theme);
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
  }, [applyPersona]);

  // theme -> page colours
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // Reminders: the backend marks them delivered when we fetch, so only ask while she is free to speak.
  useEffect(() => {
    if (!started || !online) return;
    const id = setInterval(async () => {
      if (busy.current || phaseRef.current !== "idle") return;
      try {
        const { due } = await api.remindersDue();
        if (!due.length) return;
        busy.current = true;
        try {
          for (const d of due) {
            sounds.alert();
            addLine("system", `Reminder: ${d.text}`);
            await say(`Reminder: ${d.text}`);
          }
        } finally {
          busy.current = false;
        }
      } catch {
        /* backend busy: next tick */
      }
    }, REMINDER_POLL_MS);
    return () => clearInterval(id);
  }, [started, online, say, addLine]);

  // Tell the mini orb window what we look like
  useEffect(() => {
    const c = new BroadcastChannel("nemiii");
    chan.current = c;
    c.onmessage = (e) => {
      if (e.data?.hello) c.postMessage({ state: avatarRef.current, theme: themeRef.current });
    };
    return () => {
      c.close();
      chan.current = null;
    };
  }, []);
  useEffect(() => {
    chan.current?.postMessage({ state: avatar, theme });
  }, [avatar, theme]);

  // ------------------------------------------------------------- start up
  const begin = useCallback(
    async (auto = false) => {
      speaker.current.prime();
      sounds.prime();
      setStarted(true);
      awakeUntil.current = Date.now() + AWAKE_MS;
      sounds.startup();
      const greeting = persona?.greeting || `Hello ${addressRef.current}. Systems online. What are we working on today?`;
      const ok = await say(greeting);
      if (!ok && auto) {
        setStarted(false); // the browser blocked speech: ask for one click instead
        return;
      }
      if (Listener.supported()) startWake();
      else flash("Voice input needs Chrome or Edge. You can still type.", 9000);
    },
    [say, startWake, flash, persona],
  );

  useEffect(() => {
    if (health && new URLSearchParams(window.location.search).get("auto") === "1") void begin(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [health === null]);

  // Natural offline voice: on when the backend has it and you have not switched it off.
  const naturalAvailable = !!health?.tts_natural;
  useEffect(() => {
    try {
      const saved = localStorage.getItem("nemiii.natural");
      if (saved !== null) setNaturalPref(saved === "1");
    } catch {
      /* private mode */
    }
    speaker.current.onNaturalFail = () => {
      speaker.current.natural = false;
      flash("The natural voice had a problem, so I'm using the browser voice for now.", 6000);
      setTimeout(() => { speaker.current.natural = true; }, 60_000);
    };
  }, [flash]);
  useEffect(() => {
    speaker.current.natural = naturalPref && naturalAvailable;
  }, [naturalPref, naturalAvailable]);

  // When the progress bar finishes, open the viewer so you can see what she made.
  const onMadeDone = useCallback((ok: boolean, name: string) => {  // name = file name, or the error when it failed
    setMaking(false);
    if (ok) {
      sounds.ask();
      flash(`Ready: ${name}`, 6000);
      setViewerOpen(true);
    } else flash(name ? name : "That didn't work. Check the ACTIVITY tab for the reason.", 8000);
  }, [flash]);

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
      else if (k === "t") changeTheme(THEME_ORDER[(THEME_ORDER.indexOf(themeRef.current) + 1) % THEME_ORDER.length]);
      else if (k === "p") setDrawerOpen((o) => !o);
      else if (k === "n") openMini();
      else if (k === "f") setViewerOpen((o) => !o);
      else if (k === "k") togglePause();
      else if (k === " " || k === "escape") {
        stopTalking();
        if (k === " ") e.preventDefault();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [started, wakeOn, talkOnce, startWake, stopWake, toggleGestures, lookCamera, lookScreen, changeTheme, openMini, togglePause, stopTalking]);

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
      {mode === "orb" ? (
        <OrbCanvas state={avatar} theme={theme} getLevel={getLevel} />
      ) : (
        <VideoStage state={avatar} />
      )}

      <div className="hud">
        <div className="title">
          <div className="name">N · E · M · I · I · I</div>
          <div className="sub">VOICE-CONTROLLED PC ASSISTANT</div>
          <div className="sub">
            BRAIN: {brain} · MIC: {micOn ? "ON" : "OFF"} · PC: {health?.pc_control_available ? "LINKED" : "NOT LINKED"}
          </div>
          <div className="sub">MODE: {persona?.label ?? "…"} · THEME: {THEMES[theme].label}</div>
        </div>

        <Dashboard coords={coords} online={online} />

        <Drawer open={drawerOpen} tab={tab} setTab={setTab} lines={lines} online={online} onClose={() => setDrawerOpen(false)} />

        {!online && started && <div className="banner">Backend offline. Start it with ./run.sh</div>}
        {toast && <div className="toast">{toast}</div>}

        <div className="bottom">
          {heard && <div className="heard">{heard}</div>}
          {caption && <div className="caption">{caption}</div>}
          {phase === "speaking" && (
            <div className="talkbar">
              <button onClick={togglePause} title="K">{speakPaused ? "RESUME" : "PAUSE"}</button>
              <button onClick={stopTalking} title="Space">STOP</button>
            </div>
          )}
          {confirming && (
            <div className="confirm">
              <button onClick={() => sendTyped("yes")}>YES</button>
              <button onClick={() => sendTyped("no")}>NO</button>
            </div>
          )}
        </div>

        <Creations open={viewerOpen} making={making} online={online} onClose={() => setViewerOpen(false)} onMadeDone={onMadeDone} />

        <ChatBar onSend={sendTyped} />

        <div className="controls">
          <div className="grid2">
            <button onClick={talkOnce} title="V">TALK</button>
            <button className={wakeOn ? "on" : ""} onClick={wakeOn ? stopWake : startWake} title="W">
              WAKE {wakeOn ? "ON" : "OFF"}
            </button>
            <button className={gesturesOn ? "on" : ""} onClick={() => void toggleGestures()} title="G">
              HANDS {gesturesOn ? "ON" : "OFF"}
            </button>
            <button onClick={() => setMode(mode === "orb" ? "video" : "orb")} title="M">
              {mode === "orb" ? "COME HERE" : "BACK TO ORB"}
            </button>
            <button onClick={lookCamera} title="C">LOOK</button>
            <button onClick={() => void lookScreen()} title="S">SCREEN</button>
            <button onClick={() => changeTheme(THEME_ORDER[(THEME_ORDER.indexOf(theme) + 1) % THEME_ORDER.length])} title="T">THEME</button>
            <button className={drawerOpen ? "on" : ""} onClick={() => setDrawerOpen((o) => !o)} title="P">PANEL</button>
            <button onClick={openMini} title="N">MINI ORB</button>
            <button className={viewerOpen ? "on" : ""} onClick={() => setViewerOpen((o) => !o)} title="F">CREATIONS</button>
            <button onClick={() => void cycleMode()} title="Say: switch to Jarvis">MODE</button>
            <button
              className={muted ? "" : "on"}
              onClick={() => {
                sounds.setMuted(!muted);
                setMuted(!muted);
              }}
            >
              SOUND {muted ? "OFF" : "ON"}
            </button>
            <button className={voiceReplies ? "on" : ""} onClick={() => setVoiceReplies((v) => !v)}>
              VOICE {voiceReplies ? "ON" : "OFF"}
            </button>
            {naturalAvailable && (
              <button
                className={naturalPref ? "on" : ""}
                title="Natural offline voice or the browser voice"
                onClick={() => {
                  const next = !naturalPref;
                  setNaturalPref(next);
                  try { localStorage.setItem("nemiii.natural", next ? "1" : "0"); } catch { /* ignore */ }
                }}
              >
                {naturalPref ? "NATURAL" : "BROWSER"}
              </button>
            )}
          </div>
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
            <option value="">Auto voice (matches the mode)</option>
            {voices.map((v) => (
              <option key={v.name} value={v.name}>{v.name}</option>
            ))}
          </select>
          <button className="small" onClick={() => void clearMemory()}>CLEAR CHAT</button>
        </div>

        <div className="hints">
          SAY “NEMIII / JARVIS / FRIDAY / EDITH, …” · “SWITCH TO JARVIS” · “RED ALERT” · “GOOD MORNING” · “REMIND ME IN 10 MINUTES …” · SPACE STOP · K PAUSE · F CREATIONS
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

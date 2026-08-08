"use client";

import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";

export type VoiceState = "idle" | "listening" | "thinking" | "speaking" | "error";

interface ChatResponse {
  reply: string;
  action_taken?: string | null;
  action_result?: string | null;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const VOICE_STORAGE_KEY = "nemiii-voice-uri";

export interface VoiceAssistantHandle {
  toggleListening: () => void;
  greet: () => void;
}

// Heuristic match for a female-sounding system voice. Browsers vary widely in
// what's installed — this just picks the best available, it's not guaranteed
// to find one on every machine.
const FEMALE_VOICE_HINTS = [
  "female",
  "zira", // Windows
  "samantha", // macOS
  "susan",
  "victoria",
  "karen",
  "moira",
  "tessa",
  "fiona",
  "google uk english female",
  "google us english",
  "aria", // Edge neural voices
  "jenny",
];

function pickFemaleVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  if (!voices.length) return null;
  const englishVoices = voices.filter((v) => v.lang.toLowerCase().startsWith("en"));
  const pool = englishVoices.length ? englishVoices : voices;
  for (const hint of FEMALE_VOICE_HINTS) {
    const match = pool.find((v) => v.name.toLowerCase().includes(hint));
    if (match) return match;
  }
  return pool[0];
}

// Minimal typing shim — the Web Speech API isn't in TS's lib.dom yet.
type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
};

function getSpeechRecognition(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export const VoiceAssistant = forwardRef<VoiceAssistantHandle, { onStateChange?: (s: VoiceState) => void }>(
  function VoiceAssistant({ onStateChange }, ref) {
  const [state, setState] = useState<VoiceState>("idle");
  const [transcript, setTranscript] = useState("");
  const [reply, setReply] = useState("");
  const [supported, setSupported] = useState(true);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [selectedURI, setSelectedURI] = useState<string>("");
  const [memoryCleared, setMemoryCleared] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const voiceRef = useRef<SpeechSynthesisVoice | null>(null);

  const updateState = useCallback(
    (s: VoiceState) => {
      setState(s);
      onStateChange?.(s);
    },
    [onStateChange],
  );

  useEffect(() => {
    const SpeechRecognitionCtor = getSpeechRecognition();
    if (!SpeechRecognitionCtor) {
      setSupported(false);
      return;
    }
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      setSupported(false);
      return;
    }

    const loadVoice = () => {
      const list = window.speechSynthesis.getVoices();
      setVoices(list);

      const saved = window.localStorage.getItem(VOICE_STORAGE_KEY);
      const savedVoice = saved ? list.find((v) => v.voiceURI === saved) : null;

      const chosen = savedVoice || pickFemaleVoice(list);
      voiceRef.current = chosen;
      setSelectedURI(chosen?.voiceURI ?? "");
    };
    loadVoice();
    window.speechSynthesis.onvoiceschanged = loadVoice;
    return () => {
      window.speechSynthesis.onvoiceschanged = null;
    };
  }, []);

  const handleVoiceChange = useCallback((uri: string) => {
    setSelectedURI(uri);
    const match = voices.find((v) => v.voiceURI === uri) ?? null;
    voiceRef.current = match;
    window.localStorage.setItem(VOICE_STORAGE_KEY, uri);
  }, [voices]);

  const handleClearMemory = useCallback(async () => {
    try {
      await fetch(`${BACKEND_URL}/reset_memory`, { method: "POST" });
      setMemoryCleared(true);
      setTranscript("");
      setReply("");
      setTimeout(() => setMemoryCleared(false), 1500);
    } catch {
      // silent — non-critical action, backend being briefly unreachable isn't worth surfacing
    }
  }, []);

  const speak = useCallback(
    (text: string) => {
      updateState("speaking");
      const utterance = new SpeechSynthesisUtterance(text);
      if (voiceRef.current) utterance.voice = voiceRef.current;
      utterance.pitch = 1.08;
      utterance.rate = 0.98;
      utterance.onend = () => updateState("idle");
      utterance.onerror = () => updateState("idle");
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    },
    [updateState],
  );

  const sendToBackend = useCallback(
    async (message: string) => {
      updateState("thinking");
      try {
        const res = await fetch(`${BACKEND_URL}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message }),
        });
        if (!res.ok) throw new Error(`backend returned ${res.status}`);
        const data: ChatResponse = await res.json();
        setReply(data.reply);
        speak(data.reply || "Done.");
      } catch (err) {
        updateState("error");
        const msg = err instanceof Error ? err.message : "unknown error";
        setReply(`Couldn't reach the backend (${msg})`);
        setTimeout(() => updateState("idle"), 2000);
      }
    },
    [speak, updateState],
  );

  const startListening = useCallback(() => {
    const SpeechRecognitionCtor = getSpeechRecognition();
    if (!SpeechRecognitionCtor || recognitionRef.current) return;

    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onresult = (event: any) => {
      const text = event.results[0][0].transcript;
      setTranscript(text);
      void sendToBackend(text);
    };
    recognition.onerror = () => {
      updateState("idle");
      recognitionRef.current = null;
    };
    recognition.onend = () => {
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;
    updateState("listening");
    recognition.start();
  }, [sendToBackend, updateState]);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    updateState("idle");
  }, [updateState]);

  const toggleListening = useCallback(() => {
    if (state === "listening") stopListening();
    else if (state === "idle" || state === "error") startListening();
  }, [state, startListening, stopListening]);

  const greet = useCallback(() => {
    if (state === "listening" || state === "thinking" || state === "speaking") return;
    const utterance = new SpeechSynthesisUtterance("Hello boss. Systems online. What are we on today?");
    if (voiceRef.current) utterance.voice = voiceRef.current;
    utterance.pitch = 1.08;
    utterance.rate = 0.98;
    updateState("speaking");
    utterance.onend = () => {
      updateState("idle");
      startListening();
    };
    utterance.onerror = () => updateState("idle");
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }, [state, startListening, updateState]);

  useImperativeHandle(ref, () => ({ toggleListening, greet }), [toggleListening, greet]);

  if (!supported) {
    return (
      <div className="hud-error">
        VOICE NOT SUPPORTED IN THIS BROWSER — try Chrome/Edge on the Windows host
      </div>
    );
  }

  const englishVoices = voices.filter((v) => v.lang.toLowerCase().startsWith("en"));
  const voiceOptions = englishVoices.length ? englishVoices : voices;

  return (
    <div className="voice-panel">
      <button
        type="button"
        className="hud-btn"
        onClick={toggleListening}
        disabled={state === "thinking" || state === "speaking"}
        aria-pressed={state === "listening"}
      >
        {state === "listening"
          ? "LISTENING… (click to stop)"
          : state === "thinking"
            ? "THINKING…"
            : state === "speaking"
              ? "SPEAKING…"
              : "HOLD TO TALK"}
      </button>

      {voiceOptions.length > 0 && (
        <select
          className="voice-select"
          value={selectedURI}
          onChange={(e) => handleVoiceChange(e.target.value)}
          aria-label="Voice"
        >
          {voiceOptions.map((v) => (
            <option key={v.voiceURI} value={v.voiceURI}>
              {v.name}
            </option>
          ))}
        </select>
      )}

      <button type="button" className="memory-clear-btn" onClick={handleClearMemory}>
        {memoryCleared ? "Memory cleared" : "Clear memory"}
      </button>

      {transcript && <div className="voice-transcript">“{transcript}”</div>}
      {reply && <div className="voice-reply">{reply}</div>}
    </div>
  );
  },
);

VoiceAssistant.displayName = "VoiceAssistant";

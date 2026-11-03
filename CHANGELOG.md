# Changelog

## 17
- She no longer reads symbols out loud: no "slash", "asterisk", "underscore", no web addresses or file paths, and "e.g." is said as "for example".
  The screen still shows the normal written text.
- PAUSE / RESUME and STOP buttons while she talks (also `K` and Space). Pausing never skips ahead.
- Prompt rewritten so spoken answers are short, natural, and offer "want the rest?" instead of reading everything.
- Natural offline voice (Kokoro) for all her speech, with a NATURAL / BROWSER switch and automatic fallback to the browser voice.
- Progress bar while she makes a picture, music, a voice file or a transcript (real steps from ComfyUI, MusicGen and Whisper).
- CREATIONS viewer over the orb: pictures, an audio player, transcripts, thumbnails, open in Windows. Opens when something is ready.
  Say "show my creations", press `F`.
- New endpoints: `/studio/progress`, `/studio/files`, `/studio/file/...`, `/studio/open`, `/tts`.

## 16
- Studio: catalog of free offline models sized for a 6 GB GPU, all stored on one external SSD folder (`MODELS_ROOT`).
- Voice or typed install and removal of models (asks first, checks free space, never leaves the studio folder).
- New actions: `studio_status`, `install_model`, `remove_model`, `generate_image` (ComfyUI + SDXL Turbo), `make_music` (MusicGen),
  `make_speech` (Kokoro), `transcribe_audio` (Whisper), `open_creation`, `read_transcript`.
- STUDIO tab in the side panel, `/studio` endpoint, setup/start/stop scripts, docs for the studio and for isolating OpenClaw.
- Includes the Groq vision fallback fix from v15.

## 15.0.0
**Three personalities, and a real assistant's daily tools. The orb stays.**

- Modes: Nemiii, Jarvis, Friday, Edith. "Switch to Jarvis", or call her by name. Each has its own tone, speed and voice.
- Asks before risky actions (close a program, lock, type for you, power). YES/NO buttons or say yes/no. Cancelling a shutdown never needs a confirm.
- Reminders, timers and alarms (also daily ones). Spoken when the page is open, a Windows notification when it is not.
- Daily briefing: "good morning" gives date, weather, unread mail, headlines, GitHub and today's reminders.
- Type to her: chat box, plus a side panel with CHAT, REMINDERS, ACTIVITY and MEMORY.
- Action log: everything she does is recorded and shown in the ACTIVITY tab.
- Files and clipboard: find, read (txt, md, code, docx, pdf) and open files in Documents, Downloads, Desktop. Never secrets, never programs.
- PC vitals (CPU, memory, disk, battery) and power commands with a 30 second cancel window.
- Security helpers for your own machine and LAN: port check, link check, devices on the network, newest exploited vulnerabilities (CISA), honeypot status.
- Smart home through Home Assistant (lights, switches, fans, scenes; never locks or alarms).
- Orb pulses with your real voice, four colour themes, interface sounds, a floating mini orb and a Windows tray icon.
- Plugins: drop a `.py` file in `backend/plugins/`.
- Up to 6 actions chained in one request.
- Correct local time even when WSL runs in UTC (the browser's timezone is used).
- GitHub: CI workflow, issue and PR templates, CONTRIBUTING.

## 14.0.0
- The original orb is back and much lighter (about 45 draw calls instead of about 2,400), hand tracking on the GPU.
- Groq falls back to plain mode and backup models when strict JSON fails.

## 13.0.0
- Local model (Ollama) or Groq brain, wake word, camera and screen vision, gestures, video mode, installer and desktop shortcut.

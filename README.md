# NEMIII

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)


My own AI assistant — a holographic orb interface backed by a voice
assistant that actually controls my PC — not a chatbot in a box, something
that opens apps, runs searches, plays music, checks the news, and reacts
to hand gestures across the room, built with Next.js, Three.js, MediaPipe
hand tracking on the frontend, and a FastAPI backend that bridges WSL
into real control over Windows.

Every color, the name, the voice, the memory, the gestures, every action
it can take — built and tuned by me, piece by piece.

## What it does

- **Voice**: push-to-talk, a keyboard shortcut, or a hand gesture. Speech-to-text
  and text-to-speech both run in the browser (Web Speech API) — pick your
  voice from a dropdown, it's remembered between sessions.
- **Memory**: remembers the last ~10 exchanges in a session, so follow-ups
  like "close it" after "open notepad" have context. Clear it anytime from
  the voice panel.
- **PC control**: open/close apps (anything installed, not just a fixed
  list), open URLs/folders, web search, screenshots, volume, media
  playback, lock the PC, type text, copy/paste, minimize windows, switch
  tabs, open a project in VS Code, open a GitHub repo.
- **Spoken-only answers**: ask for the news, look something up, convert
  currency, or check GitHub activity — these just answer out loud, nothing
  opens.
- **Hand gestures**: pinch-drag to spin the orb, two-hand pinch to zoom,
  double-pinch for a greeting, open-hand swipes to switch tabs or minimize
  everything.
- **Dashboard**: live weather + local news, driven by browser geolocation.
- **Auto-launch**: a Windows startup script and a desktop shortcut with a
  custom orb icon.

Full setup walkthrough, including exactly how the WSL↔Windows control
bridge works: **[NEMIII_SETUP.md](NEMIII_SETUP.md)**.

## Quick start

**Frontend:**
```bash
npm install
cp .env.local.example .env.local
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in Chrome or Edge (needs
a real browser for mic access and MediaPipe).

**Backend** (run inside WSL if your target machine is Windows):
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in your own keys — see "APIs used" below
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## APIs used

Every integration is optional except Groq — without it, the voice loop
just tells you it isn't configured instead of failing silently. Nothing
here requires a paid plan.

| Purpose | Provider | Key needed? |
| --- | --- | --- |
| Understanding speech, deciding actions | [Groq](https://console.groq.com) | Yes — required |
| News (dashboard + spoken + WhatsApp) | [NewsData.io](https://newsdata.io/register) (preferred) or [NewsAPI.org](https://newsapi.org/register) (fallback) | Yes |
| Weather | [Open-Meteo](https://open-meteo.com) | No |
| Reverse geocoding (city from coordinates) | [BigDataCloud](https://www.bigdatacloud.com/) | No |
| YouTube playback | [YouTube Data API v3](https://console.cloud.google.com/) | Yes |
| GitHub repo status | [GitHub REST API](https://docs.github.com/en/rest) | No (optional token raises rate limit) |
| Wikipedia lookups | [Wikipedia REST API](https://en.wikipedia.org/api/rest_v1/) | No |
| Currency conversion | [open.er-api.com](https://www.exchangerate-api.com/docs/free) | No |

All keys go in `backend/.env` (see `backend/.env.example` for the full list
of variable names) — never committed, it's in `.gitignore`.

## Controls

### Mouse / touch

| Input | Action |
| --- | --- |
| Drag | Spin the orb |
| Scroll / pinch | Zoom in & out |

### Hand gestures (webcam)

Press `G` (or click the gestures toggle) and allow camera access, then:

| Gesture | Action |
| --- | --- |
| Pinch (thumb + index) one hand and move it | Spin the orb |
| Pinch with **both** hands, spread apart / bring together | Zoom in / out |
| Pinch twice quickly with one hand | Greeting |
| Open hand, swipe left / right | Switch tabs |
| Open hand, swipe down | Minimize all windows |

### Keyboard

| Key | Action |
| --- | --- |
| `G` | Toggle hand gestures |
| `V` | Toggle voice listening |
| `R` | Reset the view |
| `+` / `−` | Zoom in / out |

## How it works

- **`lib/orbScene.ts`** — the Three.js scene: layered wireframe shells, a
  spiral inner core, floating code-text sprites, orbiting debris, dust
  particles, scan rings, and a bloom post-processing stack.
- **`lib/handTracker.ts`** — MediaPipe HandLandmarker on the webcam feed.
  Pinch detection with hysteresis, plus double-pinch and open-hand swipe
  detection.
- **`components/NemiiiOrb.tsx`** — the HUD and glue between the scene, the
  tracker, voice, and the dashboard.
- **`components/VoiceAssistant.tsx`** — speech-to-text/text-to-speech and
  the connection to the backend.
- **`components/InfoDashboard.tsx`** — the weather/news panel.
- **`backend/main.py`** — FastAPI server, conversation memory, routes
  requests to either `pc_control` (does something on the desktop) or
  `info_actions` (answers with information, nothing opens).
- **`backend/pc_control.py`** — every action that actually touches the
  Windows desktop, via `powershell.exe` (WSL↔Windows interop) or, for dev
  tooling, directly in WSL.
- **`backend/info_actions.py`** — news, Wikipedia, currency, GitHub —
  spoken answers with no side effects.

## License

MIT

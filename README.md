# Nemin AI Assist

A voice-controlled 3D orb assistant. Talk to it, control it with hand gestures, and let it search the web, answer questions, and control your Windows PC (open apps, open URLs, etc).

- **Frontend:** Next.js + Three.js (animated orb UI) + MediaPipe (hand gesture tracking)
- **Backend:** FastAPI + Groq (LLM with optional live web search via `groq/compound`)

---

## Features

- 🎙️ Hold-to-talk voice input (browser speech recognition)
- 🔊 Spoken replies (browser text-to-speech)
- ✋ Hand gestures (webcam): pinch + move to spin the orb, pinch with both hands to zoom, open palm (hold) to toggle talk
- 🌐 Live web search / current events (when using the `groq/compound` model)
- 🖥️ Basic PC control (e.g. "open youtube") via backend automation

---

## Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.10+
- A **Groq API key** (free) — see below
- A webcam + microphone (for gestures and voice)

---

## 1. Get a Groq API key

1. Go to **https://console.groq.com/keys**
2. Sign up / log in (free)
3. Click **Create API Key**, give it a name, and copy the key (starts with `gsk_...`)
4. Keep it somewhere safe — you'll paste it into `backend/.env` below. **Never commit this key to GitHub.**

---

## 2. Clone the repo

```bash
git clone https://github.com/neminorniel24-droid/nemin-s-FRIDAY.git
cd nemin-s-FRIDAY
```

---

## 3. Backend setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create your own `.env` file from the example:

```bash
cp .env.example .env
```

Open `backend/.env` and fill in your key:

```
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL=groq/compound
```

> `groq/compound` supports live web search, so the assistant can answer current-events questions. If you don't need that, `llama-3.3-70b-versatile` also works (faster, but no live search).

Start the backend:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Confirm it's running:

```bash
curl http://localhost:8000/health
# should return {"status":"ok"}
```

**Leave this terminal running.**

---

## 4. Frontend setup

Open a **new terminal** in the project root:

```bash
cd nemin-s-FRIDAY
npm install
```

Create your own frontend env file:

```bash
cp .env.local.example .env.local
```

Confirm `.env.local` points at your backend:

```
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

Start the frontend:

```bash
npm run dev
```

It'll print a local URL, usually:

```
Local: http://localhost:3000
```

(If port 3000 is busy, it'll automatically use 3001 — use whatever it prints.)

---

## 5. Open it

Visit the printed URL in your browser (Chrome recommended for speech + webcam support). Grant microphone and camera permissions when prompted.

- **Hold to Talk** — press and hold, speak, release
- **Gestures ON** — enables webcam hand tracking (pinch to spin/zoom, open palm hold to toggle talk)

---

## Troubleshooting

**"Couldn't reach the backend (Failed to fetch)"**
- Make sure the backend terminal shows `Uvicorn running on http://0.0.0.0:8000`
- Check `.env.local` has the right port
- Restart the frontend after changing `.env.local` (`rm -rf .next && npm run dev`) — Next.js only reads env vars at startup

**CORS error in browser console**
- Confirm `backend/main.py` has `CORSMiddleware` with your frontend's origin (or `"*"`) allowed
- Restart the backend after any changes

**`ERROR: [Errno 98] Address already in use`**
- Something else is using port 8000. Find and stop it:
  ```bash
  sudo lsof -i :8000
  kill -9 <PID>
  ```

**Assistant doesn't know current news**
- Make sure `GROQ_MODEL=groq/compound` is set in `backend/.env`, then restart uvicorn

**Gestures not detected**
- Make sure you granted camera permission and good lighting; the tracker needs a clear view of one or two hands

---

## Project structure

```
nemin-s-FRIDAY/
├── app/                  # Next.js app router pages
├── components/
│   ├── JarvisOrb.tsx     # main orb UI + gesture/voice wiring
│   └── VoiceAssistant.tsx# hold-to-talk + TTS
├── lib/
│   ├── orbScene.ts       # Three.js orb rendering
│   └── handTracker.ts    # MediaPipe gesture detection
├── backend/
│   ├── main.py           # FastAPI app, Groq calls, system prompt
│   ├── pc_control.py     # Windows PC control actions
│   └── requirements.txt
├── .env.local.example    # frontend env template
└── backend/.env.example  # backend env template
```

---

## Security note

`.env` and `.env.local` are git-ignored and must **never** be committed — they hold your Groq API key. Only the `.example` files (with placeholder values) are tracked in this repo. If you fork or clone this, always create your own `.env` files locally following the steps above.

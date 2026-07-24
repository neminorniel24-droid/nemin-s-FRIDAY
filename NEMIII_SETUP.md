# Nemiii — voice control add-on

This layers a voice assistant with Windows PC control onto the orb UI.

## Architecture (v1)

```
Browser (Chrome/Edge, Windows)
  │  Web Speech API: mic → text (STT), text → speech (TTS)
  ▼
Next.js orb UI  ──HTTP──▶  FastAPI backend (runs inside WSL)
                              │
                              ▼
                        Groq LLM decides: reply, or one whitelisted action
                              │
                              ▼
                     powershell.exe (WSL→Windows interop)
                              │
                              ▼
                   actually happens on your Windows desktop
```

No separate Windows-side agent process needed for v1 — WSL can invoke
`powershell.exe` directly as long as interop is enabled (it is, by default).

## Setup

### 1. Backend (inside WSL)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env:
#   GROQ_API_KEY            — required, from console.groq.com
#   NEWSAPI_KEY             — optional, only needed for "send me the news" —
#                             free key from newsapi.org/register
#   WHATSAPP_DEFAULT_NUMBER — optional, e.g. +91XXXXXXXXXX, used when you
#                             say "text me the news" without naming a number
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Sanity check from a Windows browser or `curl.exe` on Windows:
`http://localhost:8000/health` should return `{"ok": true, "llm_configured": true}`.
(WSL2's default networking mode forwards localhost both directions — if
`localhost` doesn't resolve from Windows, run `ip addr show eth0` inside WSL
and use that IP instead, or switch WSL to mirrored networking mode.)

### 2. Frontend

```bash
cp .env.local.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000` in Chrome or Edge **on Windows** (needs a real
browser for mic access and MediaPipe; won't work headless).

### 3. Try it

Click "HOLD TO TALK" (or press `V`), say something like:
- "open notepad" / "close spotify"
- "open my downloads folder"
- "search the web for wsl gpu passthrough"
- "what's on my screen" (screenshot → saved to Pictures)
- "lock my computer"
- "turn the volume down" / "pause the music" / "skip this song"

Use the voice dropdown next to the talk button to switch which system voice
Nemiii speaks with — your choice is remembered in the browser (localStorage)
between sessions.

Try "send me today's world news on WhatsApp" — it fetches live headlines
from NewsAPI, opens a WhatsApp chat with the default number from `.env`
(or a number you speak), and pre-fills the message. **It stops short of
pressing send** — WhatsApp's load time is too unpredictable to script a
reliable auto-send, and an unreviewed message going out isn't something
worth automating blind. Review it, then hit send yourself.

## Extending the action whitelist

Add entries to `APP_WHITELIST` and/or new functions + `ACTIONS` map in
`backend/pc_control.py`, then teach the system prompt in `backend/main.py`
about the new action so the LLM knows it exists. Keep every action as a
specific function with validated/sanitized args — don't add a generic
"run this shell command" action; that's the difference between a PC
assistant and an open remote-execution hole.

## Known v1 limitations / natural next steps

- No wake word — push-to-talk only. Adding "hey Nemiii" detection means
  either a lightweight local wake-word model (e.g. openWakeWord) always
  listening in the browser, or a native tray app.
- No conversation memory — each utterance is a fresh LLM call. Add a
  rolling message history in the backend if you want context across turns.
- `type_text` sends keystrokes to whatever window has focus on Windows —
  powerful but easy to mis-target; consider requiring the target window
  title as an argument and using `Set-Focus`-style scripting first.
- No auth on the backend — fine on localhost, not fine if you ever expose
  port 8000 beyond your own machine.

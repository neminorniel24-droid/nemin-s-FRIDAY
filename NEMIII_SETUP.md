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
#   NEWSDATA_KEY            — recommended, from newsdata.io/register
#                             (used for both the dashboard's local news and
#                              WhatsApp news — falls back to NEWSAPI_KEY if unset)
#   NEWSAPI_KEY             — optional fallback, from newsapi.org
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

## What's new in v5

- **Weather + local news dashboard** (top-right panel): on load, the
  browser asks for location permission. If granted, it shows current
  weather (via Open-Meteo, no key needed), your city (via BigDataCloud's
  free reverse-geocode, no key needed), and a few local headlines (via the
  backend's `/local_news` endpoint, which needs `NEWSDATA_KEY` or
  `NEWSAPI_KEY`). If permission is denied, there's a Retry button — it
  won't keep re-prompting on its own.
- **Open almost anything installed** — `open_app`/`close_app` no longer
  need an exact whitelist match. If the name isn't one of the fast-path
  entries, it searches everything Windows has a Start Menu shortcut for
  (`Get-StartApps`) and launches the closest match — covers Steam, PUBG,
  Discord, OBS, basically anything installed. `close_app` similarly falls
  back to a fuzzy `Get-Process` match. Both are still constrained to
  things that already exist on your machine — this generalizes *which*
  app gets opened/closed, not *what code runs*.
- **Double-pinch greeting** — pinch and release twice quickly with one
  hand (within ~0.7s) while gestures are on, and Nemiii greets you by name
  and starts listening automatically, no button press needed.

### A couple of honest caveats

- The fuzzy `close_app` match will stop *every* process whose name
  contains your search text — a vague term like "game" could catch more
  than you meant. Use specific names.
- Weather/geolocation/reverse-geocoding calls go straight from your
  browser to Open-Meteo/BigDataCloud (both free, keyless, no setup) —
  only the news portion depends on your backend keys.

## What's new in v6

- **Media key fix (for real this time)** — the earlier fix used
  `.NET`'s `SendKeys`, which doesn't reliably handle media-transport keys
  even with the char-code trick. Now using `WScript.Shell`'s `SendKeys`
  (a different, COM-based implementation) — this is the specifically
  documented approach that actually works for this key range.
- **Auto-greet on load** — Nemiii now greets you ~1.5s after the page
  finishes loading, no gesture or button needed. (If your browser blocks
  audio before any interaction on the page, the very first greeting after
  a fresh browser launch might be silent — reload once you've clicked
  anywhere on the page and it'll work normally after that.)
- **Auto-launch on boot** — `scripts/start-nemiii.sh` (runs in WSL, starts
  both backend and frontend, waits for them to be healthy, opens your
  browser) and `scripts/start-nemiii.bat` (Windows-side trigger). See
  setup steps below.

## Gmail integration (check_email)

Unlike every other integration in this project, Gmail requires an actual
login + consent flow (OAuth2), not just an API key — it's reading your
private inbox, so Google requires you to explicitly grant access.

### One-time setup

1. **console.cloud.google.com** — reuse the same project as your YouTube
   API key, or create a new one.

2. **Enable the Gmail API**: search "Gmail API" in the API Library →
   Enable. (Don't skip this — creating the OAuth client alone isn't
   enough; the API itself has to be separately enabled on the project.)

3. **Configure the OAuth consent screen** (Google Auth Platform →
   Branding, then Audience):
   - App name: anything (e.g. "Nemiii")
   - User support email + developer contact: your own email
   - User type: **External**
   - Publishing status: leave as **Testing** (avoids needing Google's
     app verification review, which isn't necessary for personal use)
   - **Test users**: add the exact Gmail address you want Nemiii reading
     mail from. This step is easy to miss and causes an
     "Access blocked... Error 403: access_denied" page if skipped.

4. **Create the OAuth client** (Clients tab → Create client):
   - Application type: **Desktop app**
   - After creating, a popup shows the Client ID/Secret —
     click **Download JSON** immediately (you can't come back for the
     secret later, though you can view/download the full client again
     from the Clients list if you miss this popup)

5. **Save the downloaded file**:
```bash
   mv /mnt/c/Users/<you>/Downloads/client_secret_*.json backend/credentials.json
```
   (Browser downloads on Windows land in the Windows Downloads folder,
   which from WSL is under `/mnt/c/Users/<you>/Downloads/`, not `~/Downloads`.)

6. **Authorize** (one time):
```bash
   cd backend
   source venv/bin/activate
   python gmail_auth.py
```
   Prints a URL — since this runs inside WSL, it likely won't auto-open a
   browser; copy the URL into your Windows browser manually. Sign in with
   the **same account** you added as a test user in step 3. On success,
   saves `token.json`, which the backend reuses automatically from then on.

`credentials.json` and `token.json` are both in `.gitignore` — never
commit either, they're your actual account credentials.

### Try it

"Check my email" / "check for unread mail" (uses Gmail search syntax,
e.g. `is:unread`, `from:someone@example.com`) — speaks back sender +
subject for the most recent matches. Read-only: this can never send,
delete, or modify anything in your mailbox.

### Setting up auto-launch

One-time build (production start is faster/more stable for autostart than
the dev server):
```bash
cd ~/friday/nemin-ai-assist
npm run build
```

Test the script manually first:
```bash
bash ~/friday/nemin-ai-assist/scripts/start-nemiii.sh
```
Check `~/friday/nemin-ai-assist/logs/backend.log` and `frontend.log` if
anything doesn't come up.

To run it automatically at login:
1. `Win+R` → `shell:startup` → Enter
2. Create a shortcut in that folder pointing at
   `scripts/start-nemiii.bat` (via its `\\wsl$\...` path, or copy the
   `.bat` to somewhere on the Windows side)

If Startup-folder timing is unreliable (WSL not ready right at login),
use Task Scheduler instead: trigger "At log on", add a 20-30 second delay,
same command.

## What's new in v8

- **"Play X on YouTube"** — actually plays the top result now, not just a
  search page. Needs a free `YOUTUBE_API_KEY` (YouTube Data API v3 — enable
  it in Google Cloud Console, console.cloud.google.com, then create an API
  key under Credentials; free tier covers ~100 searches/day). Without a
  key it still works, just opens the search results page instead of
  jumping straight to a video.

## What's new in v9

- **Conversation memory** — Nemiii now remembers the last ~10 exchanges
  within a session, so follow-ups like "open that again" or "no, the other
  one" actually have context. It's a single global in-memory list (this is
  a single-user local app, so no session IDs needed) — restarting the
  backend clears it. There's also a "Clear memory" button in the voice
  panel if you want a fresh start without restarting anything.
- **`open_and_type`** — fixes the case where typing needs to go into an app
  that isn't already open/focused. `type_text` alone only reaches whatever
  currently has focus; this opens the target app first, waits ~1.2s for it
  to load, then types. Say something like "open notepad and type hello" —
  the LLM routes that to this instead of a bare `type_text` with nothing to
  receive it.
- **Desktop shortcut with a real orb icon** — `scripts/generate_icon.py`
  rendered `assets/nemiii.ico` (a small glowing peacock-teal orb, matching
  the app's own visuals), and `scripts/create-desktop-shortcut.ps1` sets up
  a "Nemiii" shortcut on your Desktop using it.

### Setting up the desktop shortcut

Prerequisite: you already ran `npm run build` for the autostart script
(from the v6 setup). If not, do that first.

From WSL:
```bash
powershell.exe -ExecutionPolicy Bypass -File "$(wslpath -w ~/friday/nemin-ai-assist/scripts/create-desktop-shortcut.ps1)"
```

You should see `Shortcut created: C:\Users\<you>\Desktop\Nemiii.lnk`, and
a "Nemiii" icon (small glowing orb) on your Desktop. Double-click it —
same as `start-nemiii.bat`, but with a proper icon and name instead of a
generic `.bat` file.

## What's new in v10

### Two real bugs fixed
- **`open_folder` silently failed on everything** — the path was wrapped
  entirely in PowerShell single quotes, and single-quoted strings don't
  expand variables. So `$env:USERPROFILE\Downloads` was sent as a literal
  string containing the text `$env:USERPROFILE`, not your actual home
  folder — which obviously doesn't exist, so it always failed.
- **Voice always sounded confident even when actions failed** — the
  spoken reply came from the LLM's own pre-written guess, generated
  *before* the action ran, and the frontend spoke it unconditionally
  without checking whether the action actually succeeded. Now the backend
  checks the real result and corrects the reply on failure — you should
  actually hear when something didn't work.

### New: hand-gesture PC control
With gestures on (`G`), an **open hand** (not pinching) that swipes:
- **left/right** → switches tabs (`Ctrl+Tab` / `Ctrl+Shift+Tab`) in
  whatever app has focus
- **down** → minimizes all windows (show desktop)

These go through a new direct `/gesture_action` endpoint that skips the
LLM entirely — a gesture should feel instant, not wait on a model call.

### New voice/PC actions
- **Copy / paste** — "copy this" / "paste it" (sends `Ctrl+C`/`Ctrl+V` to
  whatever's focused — same real limitation as manual copy/paste: it
  copies what's currently *selected*, it can't magically grab arbitrary
  content)
- **Minimize everything**, **switch tabs** — same actions as the gestures
  above, available by voice too

### On "full control over everything"
Still holding the same line as before, and I want to say why one more
time since it came up again: I'll keep adding real, specific, testable
capabilities — this round alone added 5 new ones — but not a mode where
the LLM invents and runs arbitrary commands unchecked. That's not
foot-dragging; it's the difference between a growing feature set and a
single misheard sentence being able to do something irreversible with no
review step. If a specific task is still missing, name it and I'll build
it as a real action, same as every round so far.

## What's new in v11

### Spoken-only info actions (no browser/app opens for these)
- **"Tell me the news"** — speaks headlines directly, doesn't open
  WhatsApp or anything else. (The WhatsApp news action from before still
  exists separately, for when you actually want it sent somewhere.)
- **"What is [anything]"** — Wikipedia lookup, spoken summary. Free API,
  no key needed.
- **"Convert 100 dollars to rupees"** — currency conversion via
  open.er-api.com, free, no key. Say it as "\<amount\> \<CODE\> to \<CODE\>"
  for reliable parsing (e.g. "100 USD to INR").
- **"Check my GitHub"** — speaks your most recently updated repo names.
  Needs `GITHUB_USERNAME` in `.env` (works keyless; add `GITHUB_TOKEN`
  — a personal access token — only if you want a higher rate limit).
- **"What's the status of \<project\>"** — speaks git status + last
  commit for a project. See PROJECT_PATHS setup below.

### New PC actions
- **"Open \<project\> in VS Code"** — opens a configured project folder.
  Runs directly in WSL via the `code` CLI (VS Code's WSL-remote shell
  command), not through PowerShell — this is dev tooling, it belongs on
  the WSL side.
- **"Open my \<repo\> repo"** — opens it on github.com in the browser.

### Setting up projects and GitHub

Add to `.env`:
```
GITHUB_USERNAME=your_github_username
GITHUB_TOKEN=                          # optional, only for higher rate limits
PROJECT_PATHS=name1=/wsl/path/one,name2=/wsl/path/two
```
Example matching your actual projects:
```
PROJECT_PATHS=inr-radar=/home/nemin/inr-radar,honeypot=/home/nemin/honeypot-project,nemiii=/home/nemin/friday/nemin-ai-assist
```
Use whatever names feel natural to say — those are exactly what you'll
speak to reference them ("open inr-radar", "status of nemiii").

`open_project` needs the VS Code WSL extension installed (gives you the
`code` command inside WSL) — if you can already type `code .` in a WSL
terminal and have VS Code open, you're set.

## Known v1 limitations / natural next steps
- Gmail requires a manual one-time OAuth setup (see the Gmail section above) — it's not automatic like the other integrations.
- Conversation memory is in-process only; it resets whenever the backend restarts.


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

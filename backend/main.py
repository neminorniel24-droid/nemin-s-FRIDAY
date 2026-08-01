"""
main.py — Nemiii backend (v1, simple)

Run inside WSL:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

The Next.js frontend (running on Windows, browser does STT/TTS) sends the
recognized text here. This service asks an LLM to decide between a plain
reply and one whitelisted PC-control action, executes it via pc_control.py
(which shells out to powershell.exe on the Windows host), and returns a
reply string the frontend speaks aloud.
"""

import json
import os

from dotenv import load_dotenv

load_dotenv()  # must happen before importing pc_control/news — they read
                # their env vars (NEWSDATA_KEY, WHATSAPP_DEFAULT_NUMBER, etc.)
                # at import time, so this has to come first.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydantic import BaseModel

import pc_control
import news
import info_actions

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")  # check console.groq.com/docs/models for current options

app = FastAPI(title="Nemiii Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this once you're past local dev
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

SYSTEM_PROMPT = """You are Nemiii, a concise voice assistant that can optionally control the user's Windows PC.

Respond with ONLY a JSON object, no markdown fences, no extra text, matching this shape:
{"reply": "<what to say back, kept short and natural for speech>", "action": null}

If the user's request maps to one of these actions, fill "action" instead of null:
{"type": "open_app", "arg": "<the app name, e.g. notepad, chrome, spotify, steam, pubg, discord, obs — any installed app name works, not just common ones>"}
{"type": "close_app", "arg": "<same as open_app — the app/process name to close>"}
{"type": "open_url", "arg": "<a full http/https URL>"}
{"type": "open_folder", "arg": "<one of: documents, downloads, desktop, pictures>"}
{"type": "search_web", "arg": "<the search query text>"}
{"type": "screenshot", "arg": ""}
{"type": "set_volume", "arg": "<up|down|mute>"}
{"type": "media_control", "arg": "<play_pause|next|previous|stop>"}
{"type": "lock", "arg": ""}
{"type": "type_text", "arg": "<literal text to type into whatever window currently has focus>"}
{"type": "open_and_type", "arg": "<app_name::text to type — use this instead of type_text when the target app isn't already open/focused>"}
{"type": "send_whatsapp_news", "arg": "<phone number in +countrycode format, or empty string to use the default configured number>"}
{"type": "play_youtube", "arg": "<song or video name to play>"}
{"type": "minimize_all", "arg": ""}
{"type": "switch_tab", "arg": "<next|previous>"}
{"type": "copy_selection", "arg": ""}
{"type": "paste_clipboard", "arg": ""}
{"type": "tell_news", "arg": "<optional topic, e.g. 'technology' or 'cricket' — empty for world news. Speaks headlines directly, does not open anything.>"}
{"type": "look_up", "arg": "<any topic to look up on Wikipedia — general knowledge questions>"}
{"type": "convert_currency", "arg": "<amount and two 3-letter currency codes, e.g. '100 USD to INR'>"}
{"type": "check_github", "arg": "<GitHub username, or empty to use the configured default>"}
{"type": "project_status", "arg": "<project name from the configured list — speaks git status, doesn't open anything>"}
{"type": "open_project", "arg": "<project name from the configured list — opens it in VS Code>"}
{"type": "open_github_repo", "arg": "<repo name — opens it in the browser>"}

If nothing matches, or the user just wants conversation, set "action" to null and just reply.
Never invent action types or folder names outside the folder list above — but app names for
open_app/close_app can be anything the user names; the PC-side code resolves them against
what's actually installed."""


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    action_taken: str | None = None
    action_result: str | None = None


# Simple in-memory conversation history. This is a single-user local app,
# so one global list is fine — no need for session IDs. Capped so the
# context doesn't grow unbounded (and so older turns don't keep costing
# tokens on every single call forever).
MAX_HISTORY_MESSAGES = 20  # ~10 back-and-forth turns
conversation_history: list[dict[str, str]] = []


@app.get("/health")
def health():
    return {"ok": True, "llm_configured": client is not None}


@app.post("/reset_memory")
def reset_memory():
    conversation_history.clear()
    return {"ok": True}


@app.get("/local_news")
def local_news(query: str = "world"):
    articles, note = news.fetch_articles(query, limit=5)
    return {
        "articles": [{"title": a.title, "source": a.source} for a in articles],
        "note": note,
    }


class GestureActionRequest(BaseModel):
    type: str
    arg: str = ""


@app.post("/gesture_action")
def gesture_action(req: GestureActionRequest):
    """
    Direct action execution, no LLM involved — for hand gestures, where a
    round-trip through Groq would make the response feel laggy. Only the
    same whitelisted pc_control actions are reachable here, nothing new.
    """
    result = pc_control.execute(req.type, req.arg)
    return {"ok": result.ok, "message": result.message}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if client is None:
        return ChatResponse(reply="Backend has no GROQ_API_KEY set yet — add one to backend/.env")

    conversation_history.append({"role": "user", "content": req.message})

    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, *conversation_history],
        temperature=0.4,
        response_format={"type": "json_object"},
    )

    raw = completion.choices[0].message.content
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ChatResponse(reply="I got confused parsing that one — try again?")

    reply = parsed.get("reply", "")
    action = parsed.get("action")

    action_type = None
    action_result_text = None

    if action:
        action_type = action.get("type", "")
        arg = action.get("arg", "")

        if action_type in info_actions.INFO_ACTIONS:
            # These just answer with information — nothing opens, no
            # PowerShell involved. The answer itself becomes what's spoken.
            reply = info_actions.INFO_ACTIONS[action_type](arg)
        else:
            result = pc_control.execute(action_type, arg)
            if result.ok:
                action_result_text = result.message
            else:
                # The LLM wrote `reply` before anything actually ran, so it
                # has no way to know the action failed — without this, the
                # frontend would confidently speak success even when
                # nothing happened.
                action_result_text = f"failed: {result.message}"
                reply = f"{reply} Actually, that didn't work — {result.message}"

    # Store only the plain (and now honest, if corrected) reply text in
    # history, not the raw JSON envelope — keeps future context readable
    # and avoids the model imitating its own JSON wrapper mid-conversation.
    conversation_history.append({"role": "assistant", "content": reply})
    del conversation_history[:-MAX_HISTORY_MESSAGES]

    return ChatResponse(reply=reply, action_taken=action_type, action_result=action_result_text)

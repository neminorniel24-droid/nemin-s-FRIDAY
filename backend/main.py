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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydantic import BaseModel

import pc_control

load_dotenv()

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
{"type": "open_app", "arg": "<one of: notepad, calculator, chrome, edge, firefox, explorer, paint, settings, task_manager, vscode, spotify, camera, photos, store, terminal, whatsapp>"}
{"type": "close_app", "arg": "<same app names as open_app, only ones ending in an actual .exe>"}
{"type": "open_url", "arg": "<a full http/https URL>"}
{"type": "open_folder", "arg": "<one of: documents, downloads, desktop, pictures>"}
{"type": "search_web", "arg": "<the search query text>"}
{"type": "screenshot", "arg": ""}
{"type": "set_volume", "arg": "<up|down|mute>"}
{"type": "media_control", "arg": "<play_pause|next|previous|stop>"}
{"type": "lock", "arg": ""}
{"type": "type_text", "arg": "<literal text to type into the focused window>"}
{"type": "send_whatsapp_news", "arg": "<phone number in +countrycode format, or empty string to use the default configured number>"}

If nothing matches, or the user just wants conversation, set "action" to null and just reply.
Never invent action types or app/folder names outside these lists."""


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    action_taken: str | None = None
    action_result: str | None = None


@app.get("/health")
def health():
    return {"ok": True, "llm_configured": client is not None}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if client is None:
        return ChatResponse(reply="Backend has no GROQ_API_KEY set yet — add one to backend/.env")

    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": req.message},
        ],
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

    if not action:
        return ChatResponse(reply=reply)

    action_type = action.get("type", "")
    arg = action.get("arg", "")
    result = pc_control.execute(action_type, arg)

    return ChatResponse(
        reply=reply,
        action_taken=action_type,
        action_result=result.message if result.ok else f"failed: {result.message}",
    )

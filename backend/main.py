"""
Nemiii backend (FastAPI).

  POST /chat            talk to her (can run actions, chain up to 3)
  POST /gesture_action  hand-gesture shortcuts (no AI involved)
  POST /vision          "what do you see" for a camera / screen picture
  GET  /dashboard       weather + place + headlines for the side panel
  GET  /health          what is configured and working
  POST /reset_memory    clear the conversation (add {"all": true} to wipe saved facts too)
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import actions
import config  # loads .env first
import geo
import llm
import memory
import news
import persona
from actions import winshell

VERSION = "13"
MAX_STEPS = 3

app = FastAPI(title="Nemiii", version=VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.\d+\.\d+\.\d+)(:\d+)?",
    allow_methods=["*"], allow_headers=["*"],
)


class ChatIn(BaseModel):
    message: str
    lat: float | None = None
    lon: float | None = None


class GestureIn(BaseModel):
    name: str


class VisionIn(BaseModel):
    image: str
    question: str = ""


class ResetIn(BaseModel):
    all: bool = False


GESTURES = {
    "swipe_left": ("switch_tab", {"direction": "previous"}),
    "swipe_right": ("switch_tab", {"direction": "next"}),
    "fist": ("minimize_all", {}),
    "two_fingers": ("copy_selection", {}),
    "three_fingers": ("paste_clipboard", {}),
}


def _run_actions(parsed_actions: list[dict]) -> list[dict]:
    results = []
    for a in parsed_actions:
        res = actions.run(a["name"], a["args"])
        results.append({"name": a["name"], "kind": actions.kind_of(a["name"]) or "pc",
                        "ok": res.ok, "message": res.message})
    return results


def converse(user_text: str) -> dict:
    system = persona.build_system_prompt(actions.help_text())
    messages = [{"role": "system", "content": system}] + memory.get_history() + [
        {"role": "user", "content": user_text}]
    provider = "none"
    all_results: list[dict] = []
    reply = ""

    for step in range(MAX_STEPS):
        text, provider = llm.chat(messages, json_mode=True)
        parsed = llm.parse_reply(text)
        reply = parsed["reply"] or reply
        if not parsed["actions"]:
            break
        results = _run_actions(parsed["actions"])
        all_results += results
        info = [r for r in results if r["kind"] == "info"]
        if info and step < MAX_STEPS - 1:
            # Give the real data back to the model so she speaks facts, not guesses.
            data = "\n".join(f"[{r['name']}] {'OK' if r['ok'] else 'FAILED'}: {r['message']}" for r in info)
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": (
                "ACTION RESULTS (real data):\n" + data +
                "\nNow answer in your own words, using ONLY these results. Keep it short and spoken. "
                'Reply as JSON: {"reply": "...", "actions": []}')})
            continue
        break

    # Be honest when something failed.
    failed = [r for r in all_results if not r["ok"]]
    if failed:
        reply = "I couldn't do that. " + failed[0]["message"]
    elif not reply and all_results:
        reply = all_results[-1]["message"]
    return {"reply": reply or "Sorry, I didn't catch that.", "actions": all_results, "provider": provider}


@app.post("/chat")
def chat(body: ChatIn):
    text = body.message.strip()
    if not text:
        return {"reply": "", "actions": [], "provider": "none"}
    if body.lat is not None and body.lon is not None:
        geo.save_location(geo.last_location().get("name", "Your location"), body.lat, body.lon)
    try:
        out = converse(text)
    except RuntimeError as e:
        return {"reply": "I can't reach my language model right now.", "actions": [], "provider": "none",
                "error": str(e)}
    memory.add_message("user", text)
    memory.add_message("assistant", out["reply"])
    return out


@app.post("/gesture_action")
def gesture_action(body: GestureIn):
    spec = GESTURES.get(body.name)
    if not spec:
        return {"ok": False, "message": "unknown gesture"}
    res = actions.run(*spec)
    return {"ok": res.ok, "message": res.message}


@app.post("/vision")
def vision(body: VisionIn):
    try:
        text, provider = llm.describe_image(body.image, body.question or
                                            "Describe what you see in two short spoken sentences.")
    except RuntimeError as e:
        return {"reply": "I can't look at that right now.", "provider": "none", "error": str(e)}
    memory.add_message("user", f"[showed me a picture] {body.question}".strip())
    memory.add_message("assistant", text)
    return {"reply": text, "provider": provider}


@app.get("/dashboard")
def dashboard(lat: float | None = None, lon: float | None = None):
    loc = geo.last_location()
    if lat is not None and lon is not None:
        loc = {"name": geo.reverse_geocode(lat, lon), "lat": lat, "lon": lon}
        geo.save_location(loc["name"], lat, lon)
    out = {"place": loc["name"], "weather": None, "news": [], "errors": []}
    try:
        out["weather"] = geo.get_weather(loc["lat"], loc["lon"])
    except Exception as e:
        out["errors"].append("weather: " + str(e)[:80])
    try:
        out["news"] = news.headlines(None, 4)
    except Exception as e:
        out["errors"].append("news: " + str(e)[:80])
    return out


@app.get("/health")
def health():
    local = llm.local_status(force=True)
    base = Path(__file__).resolve().parent
    return {
        "ok": True, "version": VERSION,
        "llm_provider_setting": config.LLM_PROVIDER,
        "local": {"url": local["url"], "model": config.LOCAL_MODEL, "ready": llm.local_ready(),
                  "installed_models": local["models"]},
        "groq_configured": bool(config.GROQ_API_KEY),
        "news_provider": "newsdata+rss" if config.NEWSDATA_KEY else "rss",
        "youtube_configured": bool(config.YOUTUBE_API_KEY),
        "github_configured": bool(config.GITHUB_USERNAME),
        "gmail_signed_in": (base / "token.json").exists(),
        "pc_control_available": winshell.available(),
        "saved_facts": len(memory.get_facts()),
        "user_name": config.USER_NAME,
        "actions": sorted(actions.REGISTRY),
    }


@app.post("/reset_memory")
def reset_memory(body: ResetIn | None = None):
    if body and body.all:
        memory.clear_all()
    else:
        memory.clear_history()
    return {"ok": True}

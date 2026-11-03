"""
Nemiii backend (FastAPI).

  POST /chat               talk to her (can run actions, chain up to 6, asks before risky ones)
  POST /gesture_action     hand-gesture shortcuts (no AI involved)
  POST /vision             "what do you see" for a camera / screen picture
  GET  /dashboard          weather + place + headlines for the side panel
  GET  /health             what is configured and working
  GET/POST /mode           her personality (nemiii | jarvis | friday | edith)
  GET/POST /settings       theme
  GET  /reminders          upcoming reminders      GET /reminders/due   (the page speaks these)
  GET  /activity           the action log          GET /briefing        the morning briefing
  GET  /facts              what she remembers      POST /facts/forget
  POST /reset_memory       clear the conversation (add {"all": true} to wipe saved facts too)
"""
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import actions
import activity
import briefing
import clock
import config  # loads .env first
import geo
import llm
import memory
import news
import persona
import personas
import reminders
import router
import studio
import tts
import settings
from actions import winshell

VERSION = "17"
MAX_STEPS = 3
CONFIRM_SECONDS = 60


def _sweeper(stop: threading.Event) -> None:
    """Background: if a reminder is overdue and the page never said it, show a Windows notification."""
    def notify(title: str, text: str) -> None:
        threading.Thread(target=winshell.toast, args=(title, text), daemon=True).start()
    while not stop.wait(15):
        try:
            reminders.sweep(notify)
        except Exception:  # noqa: BLE001
            pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    stop = threading.Event()
    threading.Thread(target=_sweeper, args=(stop,), daemon=True).start()
    yield
    stop.set()


app = FastAPI(title="Nemiii", version=VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.\d+\.\d+\.\d+)(:\d+)?",
    allow_methods=["*"], allow_headers=["*"],
)

# One action list waiting for "yes" (she is a single-user local app, so one slot is enough).
PENDING: dict = {"actions": [], "expires": 0.0}


class ChatIn(BaseModel):
    message: str
    lat: float | None = None
    lon: float | None = None
    tz: str | None = None
    persona: str | None = None   # set when you call her by a mode name ("Jarvis, ...")


class GestureIn(BaseModel):
    name: str


class VisionIn(BaseModel):
    image: str
    question: str = ""


class ResetIn(BaseModel):
    all: bool = False


class ModeIn(BaseModel):
    key: str


class SettingsIn(BaseModel):
    theme: str | None = None


class ForgetIn(BaseModel):
    keyword: str


GESTURES = {
    "swipe_left": ("switch_tab", {"direction": "previous"}),
    "swipe_right": ("switch_tab", {"direction": "next"}),
    "fist": ("minimize_all", {}),
    "two_fingers": ("copy_selection", {}),
    "three_fingers": ("paste_clipboard", {}),
}


# ----------------------------------------------------------- running actions
def _confirm_prompt(pending: list[dict]) -> str:
    what = " and ".join(actions.describe(a["name"], a["args"]) for a in pending)
    if personas.current().key == "edith":
        return f"Confirm: {what}. Yes or no?"
    return f"Shall I {what}? Say yes to confirm, or no to cancel."


def _run_actions(parsed: list[dict], confirmed: bool = False, source: str = "chat") -> tuple[list[dict], str | None, dict]:
    """
    Runs the actions in order. Stops at the first RISKY one that has not been confirmed:
    that one and everything after it wait for your "yes".
    Returns (results, confirm_question_or_None, screen_changes).
    """
    results: list[dict] = []
    ui: dict = {}
    for i, a in enumerate(parsed):
        if not confirmed and actions.is_risky(a["name"], a["args"]):
            PENDING.update(actions=parsed[i:], expires=time.time() + CONFIRM_SECONDS)
            return results, _confirm_prompt(parsed[i:]), ui
        res = actions.run(a["name"], a["args"], source)
        if res.ui:
            ui.update(res.ui)
        results.append({"name": a["name"], "kind": actions.kind_of(a["name"]) or "pc",
                        "ok": res.ok, "message": res.message})
    return results, None, ui


def _pending_alive() -> bool:
    return bool(PENDING["actions"]) and time.time() < PENDING["expires"]


def _clear_pending() -> None:
    PENDING.update(actions=[], expires=0.0)


def _out(reply: str, results: list[dict], provider: str, ui: dict | None = None, confirm: bool = False, **extra) -> dict:
    return {"reply": reply, "actions": results, "provider": provider, "ui": ui or {},
            "confirm": confirm, "persona": personas.info(), **extra}


def converse(user_text: str) -> dict:
    system = persona.build_system_prompt(actions.help_text())
    messages = [{"role": "system", "content": system}] + memory.get_history() + [
        {"role": "user", "content": user_text}]
    provider = "none"
    all_results: list[dict] = []
    ui: dict = {}
    reply = ""

    for step in range(MAX_STEPS):
        text, provider = llm.chat(messages, json_mode=True)
        parsed = llm.parse_reply(text)
        reply = parsed["reply"] or reply
        if not parsed["actions"]:
            break
        results, question, step_ui = _run_actions(parsed["actions"])
        ui.update(step_ui)
        all_results += results
        if question:  # a risky action is waiting for a yes
            return _out(question, all_results, provider, ui, confirm=True)
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
    return _out(reply or "Sorry, I didn't catch that.", all_results, provider, ui)


def _fast(intent: dict) -> dict:
    """Answer an intent that needs no language model."""
    kind = intent["type"]
    if kind in ("yes", "no"):
        todo = PENDING["actions"]
        _clear_pending()
        if kind == "no":
            return _out("Cancelled." if personas.current().key != "edith" else "Cancelled.", [], "fast")
        results, _q, ui = _run_actions(todo, confirmed=True)
        failed = [r for r in results if not r["ok"]]
        reply = ("I couldn't do that. " + failed[0]["message"]) if failed else (results[-1]["message"] if results else "Done.")
        return _out(reply, results, "fast", ui)
    if kind == "persona":
        res = actions.run("set_persona", {"mode": persona_key(intent["mode"])})
        return _out(res.message, [{"name": "set_persona", "kind": "pc", "ok": res.ok, "message": res.message}],
                    "fast", res.ui)
    if kind == "theme":
        res = actions.run("set_theme", {"theme": intent["theme"]})
        return _out(res.message, [{"name": "set_theme", "kind": "pc", "ok": res.ok, "message": res.message}],
                    "fast", res.ui)
    res = actions.run("daily_briefing", {})
    return _out(res.message, [{"name": "daily_briefing", "kind": "info", "ok": res.ok, "message": res.message}], "fast")


def persona_key(word: str) -> str:
    return router.persona_for_name(word) or "nemiii"


@app.post("/chat")
def chat(body: ChatIn):
    text = body.message.strip()
    clock.remember_tz(body.tz)
    if not text:
        return _out("", [], "none")
    if body.lat is not None and body.lon is not None:
        geo.save_location(geo.last_location().get("name", "Your location"), body.lat, body.lon)
    if body.persona:
        wanted = router.persona_for_name(body.persona)
        if wanted and wanted != personas.current().key:
            personas.set_current(wanted)

    # a pending risky action that nobody confirmed in time is dropped
    if PENDING["actions"] and not _pending_alive():
        _clear_pending()

    intent = router.classify(text, _pending_alive())
    if intent:
        out = _fast(intent)
    else:
        if _pending_alive():
            _clear_pending()  # you said something else: forget the old question
        try:
            out = converse(text)
        except RuntimeError as e:
            return _out("I can't reach my language model right now.", [], "none", error=str(e))
    memory.add_message("user", text)
    memory.add_message("assistant", out["reply"])
    return out


@app.post("/gesture_action")
def gesture_action(body: GestureIn):
    spec = GESTURES.get(body.name)
    if not spec:
        return {"ok": False, "message": "unknown gesture"}
    res = actions.run(*spec, "gesture")
    return {"ok": res.ok, "message": res.message}


@app.post("/vision")
def vision(body: VisionIn):
    try:
        text, provider = llm.describe_image(body.image, body.question or
                                            "Describe what you see in two short spoken sentences.")
    except RuntimeError as e:
        return {"reply": "I can't look at that right now.", "provider": "none", "error": str(e)}
    activity.record("vision", "describe_image", {"question": body.question}, True, text)
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
def health(tz: str | None = None):
    clock.remember_tz(tz)
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
        "home_assistant_configured": bool(config.HOME_ASSISTANT_URL and config.HOME_ASSISTANT_TOKEN),
        "gmail_signed_in": (base / "token.json").exists(),
        "pc_control_available": winshell.available(),
        "tts_natural": tts.available(),
        "saved_facts": len(memory.get_facts()),
        "reminders": len(reminders.upcoming()),
        "user_name": config.USER_NAME,
        "address_as": config.ADDRESS_AS,
        "persona": personas.info(),
        "personas": [personas.info(p) for p in personas.PERSONAS.values()],
        "wake_names": personas.all_names(),
        "theme": settings.get("theme", "peacock"),
        "plugins": actions.PLUGINS,
        "actions": sorted(actions.REGISTRY),
    }


@app.get("/mode")
def get_mode():
    return personas.info()


@app.post("/mode")
def set_mode(body: ModeIn):
    p = personas.set_current(body.key)
    return personas.info(p) if p else {"error": "unknown mode"}


@app.get("/settings")
def get_settings():
    return {"theme": settings.get("theme", "peacock"), "persona": personas.current().key}


@app.post("/settings")
def put_settings(body: SettingsIn):
    if body.theme:
        from actions import ui
        key = ui.theme_key(body.theme)
        if key:
            settings.put("theme", key)
    return get_settings()


@app.get("/reminders")
def list_reminders():
    now = clock.now()
    return {"items": [{**i, "pretty": reminders.pretty(i, now)} for i in reminders.upcoming()]}


@app.get("/reminders/due")
def reminders_due():
    due = reminders.take_due()
    for i in due:
        activity.record("reminder", "reminder_due", {"text": i["text"]}, True, "spoken")
    return {"due": [{"id": i["id"], "text": i["text"]} for i in due]}


@app.delete("/reminders/{rid}")
def delete_reminder(rid: str):
    return {"ok": reminders.cancel_id(rid)}


@app.get("/activity")
def get_activity(limit: int = 50):
    return {"items": activity.recent(min(max(limit, 1), 200))}


@app.get("/studio")
def get_studio():
    """Studio panel: SSD free space and every catalog model with its install state."""
    import studio
    return {"root": config.MODELS_ROOT or None, "problem": studio.root_problem(), "free_gb": studio.free_gb(),
            "models": studio.rows(), "summary": studio.summary()}


class TtsIn(BaseModel):
    text: str


class OpenIn(BaseModel):
    folder: str
    name: str


@app.get("/studio/progress")
def studio_progress():
    """How far along the current creation is (0-100) and what she last made."""
    from actions import studio_actions as sa
    return {**studio.prog_snapshot(), "recent": [Path(i["path"]).name for i in sa.RECENT[-5:]]}


@app.get("/studio/files")
def studio_files(folder: str | None = None, limit: int = 30):
    return {"items": studio.list_outputs(folder, min(max(limit, 1), 100)), "problem": studio.root_problem()}


@app.get("/studio/file/{folder}/{name}")
def studio_file(folder: str, name: str):
    p = studio.output_path(folder, name)
    if p is None:
        raise HTTPException(404, "No such creation")
    return FileResponse(p)


@app.post("/studio/open")
def studio_open(body: OpenIn):
    from actions import studio_actions as sa
    p = studio.output_path(body.folder, body.name)
    if p is None:
        raise HTTPException(404, "No such creation")
    res = sa.open_path(p)
    return {"ok": res.ok, "message": res.message}


@app.post("/tts")
def natural_voice(body: TtsIn):
    """One sentence of natural offline speech as a WAV. The browser falls back to its own voice on any error."""
    if not tts.available():
        raise HTTPException(503, "Natural voice is not available")
    try:
        return Response(tts.synth(body.text), media_type="audio/wav")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"Natural voice failed: {str(e)[:100]}")


@app.get("/briefing")
def get_briefing():
    data = briefing.collect()
    return {"data": data, "speech": briefing.to_speech(data)}


@app.get("/facts")
def get_facts():
    return {"facts": memory.get_facts()}


@app.post("/facts/forget")
def forget_fact(body: ForgetIn):
    return {"removed": memory.forget_fact(body.keyword)}


@app.post("/reset_memory")
def reset_memory(body: ResetIn | None = None):
    if body and body.all:
        memory.clear_all()
    else:
        memory.clear_history()
    return {"ok": True}

"""
The brain. Talks to a LOCAL model (Ollama) first and falls back to Groq.

  LLM_PROVIDER=auto   local if it is running, otherwise Groq   (default)
  LLM_PROVIDER=local  local only (fully offline)
  LLM_PROVIDER=groq   cloud only
"""
import json
import re
import subprocess
import time

import requests

import config

_LOCAL_CACHE: dict = {"at": 0.0, "url": None, "models": []}
_groq_client = None


# ---------------------------------------------------------------- local model
def _candidate_urls() -> list[str]:
    urls = []
    if config.OLLAMA_URL:
        urls.append(config.OLLAMA_URL.rstrip("/"))
    urls.append("http://localhost:11434")
    # Inside WSL, Ollama installed on Windows is reachable through the Windows host IP.
    try:
        out = subprocess.run(["ip", "route"], capture_output=True, text=True, timeout=2).stdout
        m = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", out)
        if m:
            urls.append(f"http://{m.group(1)}:11434")
    except Exception:
        pass
    try:
        with open("/etc/resolv.conf") as f:
            m = re.search(r"nameserver\s+(\d+\.\d+\.\d+\.\d+)", f.read())
            if m:
                urls.append(f"http://{m.group(1)}:11434")
    except Exception:
        pass
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def local_status(force: bool = False) -> dict:
    """{'url': str|None, 'models': [names]}  (cached for 20 seconds)"""
    now = time.time()
    if not force and now - _LOCAL_CACHE["at"] < 20:
        return {"url": _LOCAL_CACHE["url"], "models": _LOCAL_CACHE["models"]}
    found_url, models = None, []
    for url in _candidate_urls():
        try:
            r = requests.get(url + "/api/tags", timeout=1.5)
            if r.ok:
                found_url = url
                models = [m.get("name", "") for m in r.json().get("models", [])]
                break
        except Exception:
            continue
    _LOCAL_CACHE.update(at=now, url=found_url, models=models)
    return {"url": found_url, "models": models}


def _has_model(models: list[str], wanted: str) -> bool:
    """'moondream' matches 'moondream:latest'; 'llama3.2:3b' must match exactly."""
    w = wanted.lower()
    return any(m.lower() == w or m.lower().startswith(w + ":") for m in models)


def local_ready() -> bool:
    st = local_status()
    return bool(st["url"]) and _has_model(st["models"], config.LOCAL_MODEL)


def _local_chat(messages: list[dict], json_mode: bool) -> str:
    st = local_status()
    payload = {
        "model": config.LOCAL_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.6},
    }
    if json_mode:
        payload["format"] = "json"
    r = requests.post(st["url"] + "/api/chat", json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["message"]["content"]


# ---------------------------------------------------------------------- Groq
def _groq():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=config.GROQ_API_KEY)
    return _groq_client


GROQ_BACKUP_MODELS = ["openai/gpt-oss-120b", "llama-3.1-8b-instant"]


def _groq_chat(messages: list[dict], json_mode: bool) -> str:
    """Strict JSON mode first; if Groq could not parse the output, retry plainly, then backup models."""
    models = [config.GROQ_MODEL] + [m for m in GROQ_BACKUP_MODELS if m != config.GROQ_MODEL]
    last = None
    for model in models:
        for strict in ([True, False] if json_mode else [False]):
            kwargs = {"model": model, "messages": messages, "temperature": 0.5}
            if strict:
                kwargs["response_format"] = {"type": "json_object"}
            if model.startswith("openai/gpt-oss"):
                kwargs["reasoning_effort"] = "low"
            try:
                resp = _groq().chat.completions.create(**kwargs)
                return resp.choices[0].message.content or ""
            except Exception as e:
                last = e
                msg = str(e).lower()
                if "401" in msg or "invalid api key" in msg:
                    raise
    raise last or RuntimeError("groq failed")


# ------------------------------------------------------------------ public API
def chat(messages: list[dict], json_mode: bool = True) -> tuple[str, str]:
    """Returns (text, provider_used). Raises RuntimeError if nothing works."""
    errors = []
    order = {"local": ["local"], "groq": ["groq"]}.get(config.LLM_PROVIDER, ["local", "groq"])
    for provider in order:
        try:
            if provider == "local":
                if not local_ready():
                    errors.append(f"local model '{config.LOCAL_MODEL}' is not running")
                    continue
                return _local_chat(messages, json_mode), "local"
            if not config.GROQ_API_KEY:
                errors.append("GROQ_API_KEY is not set")
                continue
            return _groq_chat(messages, json_mode), "groq"
        except Exception as e:  # try the next provider
            errors.append(f"{provider}: {str(e)[:200]}")
    raise RuntimeError("; ".join(errors) or "no language model available")


def describe_image(image_data_url: str, question: str) -> tuple[str, str]:
    """Look at one picture (camera frame or screenshot) and answer a question."""
    question = question or "Describe what you see, briefly."
    b64 = image_data_url.split(",", 1)[-1]
    errors = []
    order = {"local": ["local"], "groq": ["groq"]}.get(config.LLM_PROVIDER, ["local", "groq"])
    for provider in order:
        try:
            if provider == "local":
                st = local_status()
                if not st["url"] or not _has_model(st["models"], config.LOCAL_VISION_MODEL):
                    errors.append(f"local vision model '{config.LOCAL_VISION_MODEL}' not installed")
                    continue
                r = requests.post(st["url"] + "/api/chat", json={
                    "model": config.LOCAL_VISION_MODEL, "stream": False,
                    "messages": [{"role": "user", "content": question, "images": [b64]}],
                }, timeout=180)
                r.raise_for_status()
                return r.json()["message"]["content"], "local"
            if not config.GROQ_API_KEY:
                errors.append("GROQ_API_KEY is not set")
                continue
            resp = _groq().chat.completions.create(
                model=config.GROQ_VISION_MODEL,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ]}],
                temperature=0.4,
            )
            return resp.choices[0].message.content or "", "groq"
        except Exception as e:
            errors.append(f"{provider}: {str(e)[:200]}")
    raise RuntimeError("; ".join(errors))


# --------------------------------------------------------------------- parsing
def parse_reply(text: str) -> dict:
    """
    Turn the model's text into {"reply": str, "actions": [{"name","args"}]}.
    Tolerant: accepts old {"action": {...}} shape, code fences, or plain text.
    """
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    data = None
    try:
        data = json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                data = None
    if not isinstance(data, dict):
        return {"reply": text, "actions": []}

    reply = str(data.get("reply") or data.get("speech") or "").strip()
    raw = data.get("actions")
    if raw is None and data.get("action"):
        raw = [data["action"]]
    actions = []
    for a in (raw or [])[:3]:
        if isinstance(a, str):
            a = {"name": a, "args": {}}
        if isinstance(a, dict) and a.get("name"):
            args = a.get("args") or a.get("params") or {}
            actions.append({"name": str(a["name"]), "args": args if isinstance(args, dict) else {}})
    return {"reply": reply, "actions": actions}

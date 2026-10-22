"""
Central settings for Nemiii.

Everything the backend needs from the environment is read HERE, once.
Keys live in backend/.env (never commit that file). Change a value there,
restart the backend, done.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")  # must run before anything reads os.environ

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


# ---- Language model --------------------------------------------------------
# auto  = use the local model when it is running, otherwise Groq (cloud)
# local = local model only      groq = Groq only
LLM_PROVIDER = env("LLM_PROVIDER", "auto").lower()

GROQ_API_KEY = env("GROQ_API_KEY")
GROQ_MODEL = env("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_VISION_MODEL = env("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

# Local model through Ollama (https://ollama.com). Free, private, offline.
OLLAMA_URL = env("OLLAMA_URL")  # leave empty to auto-detect (localhost + Windows host)
LOCAL_MODEL = env("LOCAL_MODEL", "llama3.2:3b")
LOCAL_VISION_MODEL = env("LOCAL_VISION_MODEL", "moondream")

# ---- Other services (all optional) ------------------------------------------
NEWSDATA_KEY = env("NEWSDATA_KEY")
YOUTUBE_API_KEY = env("YOUTUBE_API_KEY")
GITHUB_USERNAME = env("GITHUB_USERNAME")
GITHUB_TOKEN = env("GITHUB_TOKEN")
WHATSAPP_DEFAULT_NUMBER = env("WHATSAPP_DEFAULT_NUMBER")  # digits only, with country code
USER_NAME = env("USER_NAME", "Nemin")
NEWS_COUNTRY = env("NEWS_COUNTRY", "in")


def project_paths() -> dict[str, str]:
    """PROJECT_PATHS=name=/path,name2=/path2  ->  {"name": "/path", ...}"""
    out: dict[str, str] = {}
    for part in env("PROJECT_PATHS").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip().lower()] = v.strip()
    return out

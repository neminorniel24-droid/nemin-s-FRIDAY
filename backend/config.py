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
GROQ_VISION_MODEL = env("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")

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
ADDRESS_AS = env("ADDRESS_AS", "boss")  # what Jarvis / Friday call you
NEWS_COUNTRY = env("NEWS_COUNTRY", "in")


def project_paths() -> dict[str, str]:
    """PROJECT_PATHS=name=/path,name2=/path2  ->  {"name": "/path", ...}"""
    out: dict[str, str] = {}
    for part in env("PROJECT_PATHS").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip().lower()] = v.strip()
    return out


# ---- v15 extras (all optional) ---------------------------------------------
# Smart home through Home Assistant (https://www.home-assistant.io): lights, switches, fans, scenes.
HOME_ASSISTANT_URL = env("HOME_ASSISTANT_URL").rstrip("/")
HOME_ASSISTANT_TOKEN = env("HOME_ASSISTANT_TOKEN")
# Name of your honeypot Docker container ("what is the honeypot doing?")
HONEYPOT_CONTAINER = env("HONEYPOT_CONTAINER", "honeypot")
# Folders she may search and read, comma separated Linux paths. Empty = your Windows
# Documents, Downloads and Desktop folders.
FILES_ROOTS = [p.strip() for p in env("FILES_ROOTS").split(",") if p.strip()]
# Fixed timezone name like Asia/Kolkata. Empty = use the one your browser reports.
TIMEZONE = env("TIMEZONE")


# ---- v16: the studio (offline models on your external SSD) --------------------
# Linux path of the folder where ALL models and creations live, e.g. /mnt/d/NemiiiStudio
# Empty = studio is off and nothing is ever downloaded.
MODELS_ROOT = env("MODELS_ROOT")
# ComfyUI (images). Empty = auto-detect on localhost and the Windows host, port 8188.
COMFY_URL = env("COMFY_URL")
# Kokoro voice used by make_speech ("af_heart", "am_michael", "bf_emma", ...)
TTS_VOICE = env("TTS_VOICE", "af_heart")
# Refuse downloads that would leave less than this much free space on the SSD (gigabytes)
MIN_FREE_GB = float(env("MIN_FREE_GB", "3") or 3)

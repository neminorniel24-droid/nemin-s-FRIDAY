"""
news.py — fetches current world headlines via NewsAPI.org.

Needs a free key from https://newsapi.org/register (no card required).
Put it in backend/.env as NEWSAPI_KEY=...
"""

from __future__ import annotations

import os

import requests

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
NEWSAPI_URL = "https://newsapi.org/v2/everything"


def fetch_world_news(limit: int = 5) -> str:
    if not NEWSAPI_KEY:
        return "News isn't set up yet — add NEWSAPI_KEY to backend/.env (free key at newsapi.org)."

    try:
        resp = requests.get(
            NEWSAPI_URL,
            params={
                "q": "world",
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": limit,
                "apiKey": NEWSAPI_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return f"Couldn't reach the news service: {e}"

    articles = data.get("articles", [])
    if not articles:
        return "No headlines came back — try again in a bit."

    lines = []
    for a in articles[:limit]:
        title = (a.get("title") or "").split(" - ")[0].strip()
        source = (a.get("source") or {}).get("name", "")
        if title:
            lines.append(f"- {title} ({source})" if source else f"- {title}")

    return "Here's what's happening around the world:\n" + "\n".join(lines)

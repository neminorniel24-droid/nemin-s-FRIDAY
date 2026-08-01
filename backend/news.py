"""
news.py — fetches news headlines, structured for both voice replies and the
frontend dashboard.

Prefers NewsData.io (broader free tier, commercial use allowed) if
NEWSDATA_KEY is set; falls back to NewsAPI.org (NEWSAPI_KEY) if not.
Get a free NewsData.io key at https://newsdata.io/register,
or a NewsAPI.org one at https://newsapi.org/register.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests

NEWSDATA_KEY = os.environ.get("NEWSDATA_KEY")
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")

NEWSDATA_URL = "https://newsdata.io/api/1/latest"
NEWSAPI_URL = "https://newsapi.org/v2/everything"


@dataclass
class Article:
    title: str
    source: str


def _fetch_newsdata(query: str, limit: int) -> tuple[list[Article] | None, str]:
    try:
        resp = requests.get(
            NEWSDATA_URL,
            params={"apikey": NEWSDATA_KEY, "q": query, "language": "en", "size": limit},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        body = ""
        if getattr(e, "response", None) is not None:
            body = f" — response: {e.response.text[:200]}"
        return None, f"NewsData request failed: {e}{body}"
    except Exception as e:  # catch anything unexpected (bad JSON, etc.) rather than hiding it
        return None, f"NewsData response error: {type(e).__name__}: {e}"

    results = data.get("results") or []
    articles = [
        Article(title=(r.get("title") or "").strip(), source=(r.get("source_id") or ""))
        for r in results[:limit]
        if r.get("title")
    ]
    return articles, "" if articles else "NewsData returned no usable results"


def _fetch_newsapi(query: str, limit: int) -> tuple[list[Article] | None, str]:
    try:
        resp = requests.get(
            NEWSAPI_URL,
            params={
                "q": query,
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
        body = ""
        if getattr(e, "response", None) is not None:
            body = f" — response: {e.response.text[:200]}"
        return None, f"NewsAPI request failed: {e}{body}"
    except Exception as e:
        return None, f"NewsAPI response error: {type(e).__name__}: {e}"

    articles = data.get("articles") or []
    parsed = [
        Article(
            title=(a.get("title") or "").split(" - ")[0].strip(),
            source=(a.get("source") or {}).get("name", ""),
        )
        for a in articles[:limit]
        if a.get("title")
    ]
    return parsed, "" if parsed else "NewsAPI returned no usable results"


def fetch_articles(query: str, limit: int = 5) -> tuple[list[Article], str]:
    """Returns (articles, note). Note is empty on success, otherwise a
    real, specific explanation — safe to show directly to the user."""
    errors = []

    if NEWSDATA_KEY:
        articles, err = _fetch_newsdata(query, limit)
        if articles:
            return articles, ""
        errors.append(err)

    if NEWSAPI_KEY:
        articles, err = _fetch_newsapi(query, limit)
        if articles:
            return articles, ""
        errors.append(err)

    if not NEWSDATA_KEY and not NEWSAPI_KEY:
        return [], "No news API key configured — add NEWSDATA_KEY or NEWSAPI_KEY to backend/.env."
    return [], " | ".join(e for e in errors if e) or "Couldn't fetch news right now — try again shortly."


def fetch_world_news(limit: int = 5) -> str:
    """Formatted string for voice replies / WhatsApp text."""
    articles, note = fetch_articles("world", limit)
    if note:
        return note
    lines = [f"- {a.title}" + (f" ({a.source})" if a.source else "") for a in articles]
    return "Here's what's happening around the world:\n" + "\n".join(lines)

"""
info_actions.py — actions that answer with spoken information rather than
doing something on the Windows desktop. No PowerShell involved here; these
just fetch data and hand back text for Nemiii to say out loud.

All free, no-key APIs except GitHub (works keyless for public data, but a
token raises the very low unauthenticated rate limit if you add one).
"""

from __future__ import annotations

import os
import re
import subprocess
import urllib.parse

import requests

import news
import pc_control

GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")  # optional — raises rate limit if set


def tell_news(topic: str) -> str:
    """Speaks headlines directly — no browser, no WhatsApp, just the answer."""
    query = topic.strip() or "world"
    articles, note = news.fetch_articles(query, limit=5)
    if note:
        return note
    lines = [a.title for a in articles]
    return f"Here's the latest on {query}: " + "; ".join(lines)


def look_up(query: str) -> str:
    """Wikipedia summary lookup — free, no key, no rate limit for personal use."""
    if not query.strip():
        return "What would you like me to look up?"
    try:
        title = urllib.parse.quote(query.strip().replace(" ", "_"))
        resp = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}",
            timeout=10,
            headers={"User-Agent": "Nemiii-personal-assistant"},
        )
        if resp.status_code == 404:
            return f"I couldn't find a Wikipedia page for '{query}'."
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return f"Lookup failed: {e}"

    extract = data.get("extract", "")
    if not extract:
        return f"Found the page for '{query}' but there's no summary available."
    return extract


CURRENCY_PATTERN = re.compile(
    r"([\d.]+)\s*([a-zA-Z]{3})\s*(?:to|in)\s*([a-zA-Z]{3})", re.IGNORECASE
)


def convert_currency(arg: str) -> str:
    """Expects arg like '100 USD to INR'. Uses open.er-api.com — free, no key."""
    match = CURRENCY_PATTERN.search(arg)
    if not match:
        return "I need an amount and two currency codes, like '100 USD to INR'."

    amount_str, from_cur, to_cur = match.groups()
    amount = float(amount_str)
    from_cur, to_cur = from_cur.upper(), to_cur.upper()

    try:
        resp = requests.get(f"https://open.er-api.com/v6/latest/{from_cur}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return f"Currency lookup failed: {e}"

    rates = data.get("rates", {})
    if to_cur not in rates:
        return f"I don't have a rate for {to_cur}."

    converted = amount * rates[to_cur]
    return f"{amount:g} {from_cur} is about {converted:,.2f} {to_cur}."


def check_github(username_arg: str) -> str:
    """Speaks a summary of recent repo activity — no browser opened."""
    username = username_arg.strip() or GITHUB_USERNAME
    if not username:
        return "No GitHub username configured — add GITHUB_USERNAME to backend/.env, or say whose account to check."

    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    try:
        resp = requests.get(
            f"https://api.github.com/users/{username}/repos",
            params={"sort": "updated", "per_page": 5},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        repos = resp.json()
    except requests.RequestException as e:
        return f"GitHub lookup failed: {e}"

    if not repos:
        return f"No public repos found for {username}."

    names = [r["name"] for r in repos]
    return f"Your most recently updated repos are: {', '.join(names)}."


def project_status(name: str) -> str:
    """Speaks git status for a configured project — same PROJECT_PATHS
    whitelist as the open_project PC action."""
    path = pc_control.PROJECT_WHITELIST.get(name.strip().lower())
    if not path:
        return f"'{name}' isn't configured — add it to PROJECT_PATHS in backend/.env"

    try:
        status = subprocess.run(
            ["git", "-C", path, "status", "--short"], capture_output=True, text=True, timeout=10
        )
        log = subprocess.run(
            ["git", "-C", path, "log", "-1", "--oneline"], capture_output=True, text=True, timeout=10
        )
    except FileNotFoundError:
        return "git isn't available in this environment."
    except subprocess.TimeoutExpired:
        return "Git command timed out."

    if status.returncode != 0:
        return f"'{name}' doesn't look like a git repo, or: {status.stderr.strip()}"

    changes = status.stdout.strip()
    last_commit = log.stdout.strip() or "no commits yet"
    if changes:
        n_changed = len(changes.splitlines())
        return f"{name}: {n_changed} uncommitted change{'s' if n_changed != 1 else ''}. Last commit: {last_commit}."
    return f"{name} is clean, nothing pending. Last commit: {last_commit}."


INFO_ACTIONS = {
    "tell_news": tell_news,
    "look_up": look_up,
    "convert_currency": convert_currency,
    "check_github": check_github,
    "project_status": project_status,
}

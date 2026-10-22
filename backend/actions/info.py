"""
Actions that FETCH information. The result text goes back to the language model,
which then says it out loud, so she only speaks real data, never guesses.
"""
import ast
import operator
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests

import config
import geo
import memory
import news
from . import Result, action

UA = {"User-Agent": "Nemiii/13 (personal assistant)"}


@action("tell_news", "info", 'Get today\'s real headlines. args: {"topic": "optional, e.g. cricket or technology"}')
def tell_news(a: dict) -> Result:
    topic = str(a.get("topic") or "").strip() or None
    items = news.headlines(topic, 5)
    if not items:
        return Result(False, "I couldn't get any headlines right now.")
    lines = [f"{i['title']} ({i['source']})" if i["source"] else i["title"] for i in items]
    return Result(True, "Headlines:\n" + "\n".join(lines))


@action("weather", "info", 'Current weather. args: {"city": "optional; defaults to where you are"}')
def weather(a: dict) -> Result:
    city = str(a.get("city") or "").strip()
    if city:
        place = geo.geocode(city)
        if not place:
            return Result(False, f"I couldn't find a place called {city}.")
    else:
        place = geo.last_location()
    w = geo.get_weather(place["lat"], place["lon"])
    return Result(True, (
        f"Weather in {place['name']}: {w['text']}, {w['temp_c']} degrees Celsius "
        f"(feels like {w['feels_c']}), humidity {w['humidity']} percent, wind {w['wind_kmh']} km/h."))


@action("time_now", "info", "Current date and time. args: {}")
def time_now(a: dict) -> Result:
    return Result(True, datetime.now().strftime("It is %A, %d %B %Y, %I:%M %p."))


@action("look_up", "info", 'Look something up on Wikipedia. args: {"topic": "..."}')
def look_up(a: dict) -> Result:
    topic = str(a.get("topic", "")).strip()
    if not topic:
        return Result(False, "What should I look up?")
    s = requests.get("https://en.wikipedia.org/w/api.php", params={
        "action": "opensearch", "search": topic, "limit": 1, "format": "json"}, headers=UA, timeout=8).json()
    if not s[1]:
        return Result(False, f"I found nothing on Wikipedia for {topic}.")
    summary = requests.get("https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(s[1][0].replace(" ", "_")),
                           headers=UA, timeout=8).json()
    text = summary.get("extract") or ""
    return Result(True, f"{s[1][0]}: {text[:700]}") if text else Result(False, "That page had no summary.")


@action("convert_currency", "info", 'Convert money. args: {"amount": 100, "from": "USD", "to": "INR"}')
def convert_currency(a: dict) -> Result:
    amount = float(a.get("amount", 1))
    src, dst = str(a.get("from", "USD")).upper(), str(a.get("to", "INR")).upper()
    r = requests.get(f"https://open.er-api.com/v6/latest/{src}", timeout=8).json()
    rate = (r.get("rates") or {}).get(dst)
    if not rate:
        return Result(False, f"I couldn't get the rate from {src} to {dst}.")
    return Result(True, f"{amount:g} {src} is about {amount * rate:,.2f} {dst} (1 {src} = {rate:.4f} {dst}).")


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod, ast.USub: operator.neg, ast.FloorDiv: operator.floordiv}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        if isinstance(node.op, ast.Pow) and abs(_eval(node.right)) > 100:
            raise ValueError("exponent too large")
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported")


@action("calculate", "info", 'Do arithmetic exactly. args: {"expression": "12.5 * (3 + 4)"}')
def calculate(a: dict) -> Result:
    expr = str(a.get("expression", "")).replace("^", "**").replace("x", "*")
    try:
        value = _eval(ast.parse(expr, mode="eval").body)
    except Exception:
        return Result(False, "I couldn't work that sum out.")
    return Result(True, f"{expr} = {value:,.6g}")


@action("check_github", "info", "Your latest GitHub repositories and activity. args: {}")
def check_github(a: dict) -> Result:
    if not config.GITHUB_USERNAME:
        return Result(False, "GITHUB_USERNAME isn't set.")
    headers = dict(UA)
    if config.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    r = requests.get(f"https://api.github.com/users/{config.GITHUB_USERNAME}/repos",
                     params={"sort": "pushed", "per_page": 5}, headers=headers, timeout=8)
    r.raise_for_status()
    lines = [f"{x['name']} (pushed {x['pushed_at'][:10]}, {x['open_issues_count']} open issues)" for x in r.json()]
    return Result(True, "Most recently pushed repositories:\n" + "\n".join(lines))


@action("project_status", "info", 'Git status of one of your projects. args: {"name": "<project name>"}')
def project_status(a: dict) -> Result:
    name = str(a.get("name", "")).lower().strip()
    paths = config.project_paths()
    path = paths.get(name) or next((p for k, p in paths.items() if name and name in k), None)
    if not path or not Path(path).exists():
        return Result(False, f"I don't know a project called {name}. Known: {', '.join(paths) or 'none'}.")
    def git(*args):
        return subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, timeout=10).stdout.strip()
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    changed = [l for l in git("status", "--porcelain").splitlines() if l.strip()]
    last = git("log", "-1", "--pretty=%s (%cr)")
    return Result(True, f"Project {name}: on branch {branch}, {len(changed)} changed files. Last commit: {last}.")


@action("check_email", "info", "Count and read out unread Gmail. args: {}")
def check_email(a: dict) -> Result:
    import gmail_client
    total, msgs = gmail_client.unread(5)
    if not msgs:
        return Result(True, "No unread emails.")
    lines = [f"from {m['from']}: {m['subject']}" for m in msgs]
    return Result(True, f"About {total} unread. Latest:\n" + "\n".join(lines))


@action("remember", "info", 'Save something to remember forever. args: {"fact": "..."}')
def remember(a: dict) -> Result:
    ok = memory.add_fact(str(a.get("fact", "")))
    return Result(ok, "Saved. I'll remember that." if ok else "There was nothing to save.")


@action("forget", "info", 'Forget saved facts that mention a word. args: {"keyword": "..."}')
def forget(a: dict) -> Result:
    n = memory.forget_fact(str(a.get("keyword", "")))
    return Result(True, f"Forgot {n} saved item{'s' if n != 1 else ''}.")

"""
The daily briefing: weather, mail, headlines, GitHub and today's reminders in one go.
Each part is optional. If one fails she simply skips it, so the briefing always works.
"""
import config
import clock
import geo
import news
import personas
import reminders


def collect() -> dict:
    now = clock.now()
    data: dict = {"date": now.strftime("%A, %d %B"), "time": now.strftime("%I:%M %p").lstrip("0"),
                  "place": None, "weather": None, "unread": None, "mail": [], "headlines": [],
                  "github": None, "reminders": [], "skipped": []}
    try:
        loc = geo.last_location()
        w = geo.get_weather(loc["lat"], loc["lon"])
        data["place"] = loc["name"]
        data["weather"] = f"{w['text']}, {w['temp_c']} degrees"
    except Exception:
        data["skipped"].append("weather")
    try:
        import gmail_client
        total, msgs = gmail_client.unread(3)
        data["unread"] = total
        data["mail"] = [f"{m['subject']}" for m in msgs]
    except Exception:
        data["skipped"].append("mail")
    try:
        data["headlines"] = [h["title"] for h in news.headlines(None, 3)]
    except Exception:
        data["skipped"].append("news")
    if config.GITHUB_USERNAME:
        try:
            import requests
            r = requests.get(f"https://api.github.com/users/{config.GITHUB_USERNAME}/repos",
                             params={"sort": "pushed", "per_page": 1}, timeout=6,
                             headers={"User-Agent": "Nemiii"})
            r.raise_for_status()
            repo = r.json()[0]
            data["github"] = f"{repo['name']}, last pushed {repo['pushed_at'][:10]}"
        except Exception:
            data["skipped"].append("github")
    data["reminders"] = [reminders.pretty(i, now) for i in reminders.today(now)]
    return data


def to_speech(d: dict) -> str:
    p = personas.current().key
    who = config.ADDRESS_AS
    hour = clock.now().hour
    part = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
    opener = {"friday": f"Briefing, {who}.", "edith": "Briefing."}.get(p, f"Good {part}, {who}.")
    parts = [opener, f"It is {d['date']}, {d['time']}."]
    if d["weather"]:
        parts.append(f"In {d['place']} it is {d['weather']}.")
    if d["unread"] is not None:
        if d["unread"]:
            parts.append(f"You have {d['unread']} unread email{'s' if d['unread'] != 1 else ''}. "
                         f"The latest is {d['mail'][0]}." if d["mail"] else f"You have {d['unread']} unread emails.")
        else:
            parts.append("Your inbox is clear.")
    if d["reminders"]:
        parts.append("Today: " + "; ".join(d["reminders"]) + ".")
    else:
        parts.append("No reminders today.")
    if d["headlines"]:
        parts.append("Top headlines. " + " ".join(h.rstrip(".") + "." for h in d["headlines"]))
    if d["github"]:
        parts.append(f"On GitHub, your latest project is {d['github']}.")
    return " ".join(parts)

"""Reminders, timers, the daily briefing, the activity log and a tiny pause between steps."""
import time

import activity
import briefing
import clock
import reminders
from . import Result, action


@action("set_reminder", "info",
        'Remind him later or set an alarm. args: {"text": "call mom", "minutes": 20} or {"text": "...", "at": "18:30"} '
        'or {"text": "...", "at": "tomorrow 7:00"}; add "repeat": "daily" for every day')
def set_reminder(a: dict) -> Result:
    text = str(a.get("text") or a.get("label") or "").strip()
    due = reminders.parse_when(a)
    if due is None:
        return Result(False, "I couldn't tell when. Say something like in twenty minutes, or at six thirty.")
    item = reminders.add(text or "Reminder", due, str(a.get("repeat") or ""))
    return Result(True, "Reminder set: " + reminders.pretty(item) + ".")


@action("set_timer", "info", 'Start a countdown timer. args: {"minutes": 10, "label": "tea"} (or "seconds")')
def set_timer(a: dict) -> Result:
    due = reminders.parse_when(a)
    if due is None:
        return Result(False, "How long should the timer run?")
    label = str(a.get("label") or "Timer").strip()
    reminders.add(f"{label} is done", due)
    secs = round((due - clock.now()).total_seconds())
    span = f"{secs // 60} minute{'s' if secs // 60 != 1 else ''}" if secs >= 120 else f"{secs} seconds"
    return Result(True, f"Timer set for {span}.")


@action("list_reminders", "info", "Read out his upcoming reminders and alarms. args: {}")
def list_reminders(a: dict) -> Result:
    items = reminders.upcoming()
    if not items:
        return Result(True, "You have no reminders.")
    return Result(True, "Upcoming:\n" + "\n".join(reminders.pretty(i) for i in items[:8]))


@action("cancel_reminder", "info", 'Cancel reminders that mention a word, or all. args: {"keyword": "call mom" | "all"}')
def cancel_reminder(a: dict) -> Result:
    n = reminders.cancel(str(a.get("keyword") or ""))
    return Result(True, f"Cancelled {n} reminder{'s' if n != 1 else ''}.")


@action("daily_briefing", "info",
        "Morning briefing: date, weather, unread email, headlines, GitHub and today's reminders. args: {}")
def daily_briefing(a: dict) -> Result:
    return Result(True, briefing.to_speech(briefing.collect()))


@action("activity_summary", "info", "What she has done recently (the action log). args: {}")
def activity_summary(a: dict) -> Result:
    return Result(True, activity.summary_text())


@action("wait", "pc", 'Pause between steps so a program can open. args: {"seconds": 1-10}')
def wait(a: dict) -> Result:
    try:
        secs = max(0.2, min(10.0, float(a.get("seconds", 1))))
    except (TypeError, ValueError):
        secs = 1.0
    time.sleep(secs)
    return Result(True, "Done.")

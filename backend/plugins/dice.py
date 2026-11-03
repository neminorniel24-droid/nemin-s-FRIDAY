"""
Example plugin. Drop a .py file in this folder, restart the backend, and she gets a new ability.
Files whose name starts with _ are ignored. Copy this file to start your own.
"""
import random

from actions import Result, action


@action("roll_dice", "info", 'Roll dice. args: {"sides": 6, "count": 1}')
def roll_dice(a: dict) -> Result:
    sides = max(2, min(1000, int(a.get("sides", 6))))
    count = max(1, min(10, int(a.get("count", 1))))
    rolls = [random.randint(1, sides) for _ in range(count)]
    return Result(True, f"Rolled {count} d{sides}: {', '.join(map(str, rolls))} (total {sum(rolls)}).")

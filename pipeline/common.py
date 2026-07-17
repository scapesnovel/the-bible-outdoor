#!/usr/bin/env python3
"""Shared helpers for the Rooted Daily pipeline."""
import json, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ASSETS = ROOT / "assets"
OUT = ROOT / "output"

CHANNEL_NAME = "Rooted Daily"
HANDLE = "@RootedDailyFaith"

def load_plan():
    return json.loads((DATA / "plan.json").read_text())

def load_verses():
    return json.loads((DATA / "verses.json").read_text())

def get_day_entry(day_number=None):
    """Pick today's entry. Cycles through the plan indefinitely (day 32 -> day 1 etc.)."""
    plan = load_plan()
    days = plan["days"]
    if day_number is None:
        start = datetime.date.fromisoformat(plan["channel"]["start_date"])
        today = datetime.date.today()
        idx = (today - start).days
        if idx < 0:
            idx = 0
        day_number = (idx % len(days)) + 1
    entry = days[day_number - 1]
    return plan, entry, day_number

def display_ref(ref):
    """Psalms 46:1-3 -> Psalm 46:1-3 for natural display."""
    return ref.replace("Psalms ", "Psalm ")

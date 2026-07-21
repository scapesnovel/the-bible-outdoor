#!/usr/bin/env python3
"""Shared helpers for the The Bible Outdoor pipeline."""
import json, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ASSETS = ROOT / "assets"
OUT = ROOT / "output"

CHANNEL_NAME = "The Bible Outdoor"
HANDLE = "@TheBibleOutdoor"

def load_plan():
    return json.loads((DATA / "plan.json").read_text())

def load_config():
    p = DATA / "config.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"mode": "full", "shorts_per_day": 1}

def load_verses():
    return json.loads((DATA / "verses.json").read_text())

STATE_PATH = DATA / "state.json"

def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"published": []}  # list of {"date","day","cycle","longform_id","short_id"}

def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=1))

def today_str():
    return datetime.date.today().isoformat()

def already_published_today(state):
    """Shorts mode: done when at least one Short is live today.
    Full mode: done when both long-form and Short are live."""
    for p in state["published"]:
        if p["date"] != today_str():
            continue
        if p.get("mode") == "shorts":
            if p.get("short_ids") or p.get("short_id"):
                return True
        elif p.get("longform_id") and p.get("short_id"):
            return True
    return False

def next_slot(state, total_days):
    """Next (day, cycle) that has never been published. Never repeats:
    cycle 1 = days 1..31, cycle 2 = days 1..31 with variation, etc."""
    n = len([p for p in state["published"]
             if p.get("longform_id") or p.get("short_ids") or p.get("short_id")])
    return (n % total_days) + 1, (n // total_days) + 1

def get_day_entry(day_number=None, cycle=1):
    """Pick an entry. In cycle>1 the content varies (different Short verse,
    reshuffled passage order, alternate title angle) so nothing repeats."""
    plan = load_plan()
    days = plan["days"]
    if day_number is None:
        state = load_state()
        day_number, cycle = next_slot(state, len(days))
    entry = json.loads(json.dumps(days[day_number - 1]))  # deep copy
    if cycle > 1:
        import random
        rng = random.Random(cycle * 1000 + day_number)
        rng.shuffle(entry["passages"])
        # different verse becomes the Short each cycle
        alt = entry["passages"][(cycle - 1) % len(entry["passages"])]
        entry["short"] = {"ref": alt["ref"],
                          "hook": f"A verse about {entry['keywords'][0]} you need today.",
                          "reflection": alt["reflection"][:220]}
        entry["_cycle"] = cycle
    return plan, entry, day_number

def display_ref(ref):
    """Psalms 46:1-3 -> Psalm 46:1-3 for natural display."""
    return ref.replace("Psalms ", "Psalm ")

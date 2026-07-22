#!/usr/bin/env python3
"""Daily orchestrator — stateful, idempotent, never repeats content.

Modes (data/config.json):
  "shorts" (current growth phase): builds & uploads 2 Shorts/day
      * Short A -> 13:00 UTC (= 9am New York morning scroll)
      * Short B -> 22:00 UTC (= 6pm New York evening scroll / late EU)
  "full": adds the daily long-form meditation
      * Long-form -> 10:45 UTC premiere, Short -> 16:00 UTC

- Picks the next unpublished (day, cycle) slot from data/state.json
- Records video IDs + used verses in committed state, so a re-run the
  same day is a safe no-op and no verse is ever repeated.
"""
import sys, os, json, pathlib, datetime, traceback
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import (OUT, load_state, save_state, next_slot, load_plan,
                    load_config, today_str, already_published_today)
import verse_picker as vp
import custom as custom_mod

LONGFORM_UTC = (10, 45)
SHORT_UTC = (16, 0)
SHORT_A_UTC = (13, 0)   # 9am New York — morning scroll
SHORT_B_UTC = (22, 0)   # 6pm New York — evening scroll

def publish_at(hh_mm):
    now = datetime.datetime.now(datetime.timezone.utc)
    t = now.replace(hour=hh_mm[0], minute=hh_mm[1], second=0, microsecond=0)
    if t <= now + datetime.timedelta(minutes=10):
        t += datetime.timedelta(days=1)
    return t.isoformat().replace("+00:00", "Z")

def _customs_today():
    """Owner-scheduled custom Shorts whose publish date is today (UTC).
    Returns their publish datetimes."""
    q = custom_mod.load_queue()
    out = []
    for x in q.get("queue", []):
        if x.get("status") in ("pending", "scheduled"):
            try:
                t = datetime.datetime.fromisoformat(x["publish_at"].replace("Z", "+00:00"))
            except Exception:
                continue
            if t.date().isoformat() == today_str():
                out.append(t)
    return out

def _bot_slots_avoiding(customs, n):
    """Pick n publish slots from the candidate grid keeping >= MIN_GAP_HOURS
    from every custom Short and from each other."""
    gap = custom_mod.MIN_GAP_HOURS
    candidates = [(13, 0), (22, 0), (16, 0), (18, 0), (20, 0), (11, 0)]
    chosen = []
    def ok(hh_mm):
        t = datetime.datetime.now(datetime.timezone.utc).replace(
            hour=hh_mm[0], minute=hh_mm[1], second=0, microsecond=0)
        for c in customs:
            if abs((t - c).total_seconds()) / 3600 < gap:
                return False
        for s in chosen:
            ts = datetime.datetime.now(datetime.timezone.utc).replace(
                hour=s[0], minute=s[1], second=0, microsecond=0)
            if abs((t - ts).total_seconds()) / 3600 < gap:
                return False
        return True
    for c in candidates:
        if len(chosen) >= n:
            break
        if ok(c):
            chosen.append(c)
    return chosen

def _burn_ledger(refs):
    used = vp.load_ledger()
    used.update(refs)
    vp.save_ledger(used)
    return len(used)

def main(force_day=None, do_upload=True):
    state = load_state()
    plan = load_plan()
    cfg = load_config()

    if do_upload and already_published_today(state):
        print(f"Already published today ({today_str()}). Nothing to do — safe exit.")
        return

    if force_day:
        day, cycle = force_day, 1
    else:
        day, cycle = next_slot(state, len(plan["days"]))

    entry = plan["days"][day - 1]
    ep = (cycle - 1) * len(plan["days"]) + day
    mode = cfg.get("mode", "full")
    print(f"=== The Bible Outdoor — Episode {ep} (day {day}, cycle {cycle}, mode={mode}): {entry['theme']} ===")

    import build_short
    final_dir = OUT / f"day{day:02d}"

    if mode == "shorts":
        # ---- Shorts-only growth phase: 2 Shorts/day ----
        n = int(cfg.get("shorts_per_day", 2))

        # Owner displacement rules: each custom Short scheduled today replaces
        # one bot Short. Displaced verses aren't lost — they only burn on
        # upload, so they stay in the pool for a future day.
        customs = _customs_today()
        if customs:
            n = max(0, n - len(customs))
            print(f"Owner has {len(customs)} custom Short(s) today -> bot builds {n}.")
        if n == 0:
            print("Day fully covered by custom Shorts. Bot skips — resumes next day.")
            return

        built = []
        for i in range(n):
            path, meta = build_short.build(day, cycle, variant=i)
            built.append((path, meta))
        if not do_upload:
            print("Build-only mode; skipping upload.")
            return
        import upload
        slots = (_bot_slots_avoiding(customs, n) if customs
                 else [SHORT_A_UTC, SHORT_B_UTC, (18, 0), (20, 0)])
        if len(slots) < n:
            slots += [(20, 0), (18, 0)]  # emergency fallback, still same-day
        record = {"date": today_str(), "day": day, "cycle": cycle, "episode": ep,
                  "theme": entry["theme"], "mode": "shorts", "short_ids": [],
                  "verse_refs": []}
        failures = 0
        for i, (path, meta) in enumerate(built):
            suffix = "" if i == 0 else f"_{chr(ord('a') + i)}"
            try:
                vid = upload.upload(final_dir / f"short{suffix}_meta.json", None,
                                    publish_at_iso=publish_at(slots[i % len(slots)]))
                record["short_ids"].append(vid)
                record["verse_refs"] += meta["verse_refs"]
            except Exception:
                failures += 1
                traceback.print_exc()
        if record["short_ids"]:
            total = _burn_ledger(record["verse_refs"])
            # state compatibility: mark day complete when at least one Short is live
            record["longform_id"] = None
            record["short_id"] = record["short_ids"][0]
            state["published"].append(record)
            save_state(state)
            print(f"State saved: episode {ep}, {len(record['short_ids'])} Shorts, "
                  f"{len(record['verse_refs'])} verses burned (ledger: {total}).")
        if failures:
            sys.exit(1)
        return

    # ---- Full mode: long-form + Short ----
    import build_longform, build_thumbnail
    lf_path, lf_meta = build_longform.build(day, cycle)
    sh_path, sh_meta = build_short.build(day, cycle)
    thumb = build_thumbnail.build(day)

    if not do_upload:
        print("Build-only mode; skipping upload.")
        return

    import upload
    record = {"date": today_str(), "day": day, "cycle": cycle, "episode": ep,
              "theme": entry["theme"], "mode": "full",
              "longform_id": None, "short_id": None}
    failures = 0
    try:
        record["longform_id"] = upload.upload(final_dir / "longform_meta.json", thumb,
                                              publish_at_iso=publish_at(LONGFORM_UTC))
    except Exception:
        failures += 1
        traceback.print_exc()
    try:
        record["short_id"] = upload.upload(final_dir / "short_meta.json", None,
                                           publish_at_iso=publish_at(SHORT_UTC))
    except Exception:
        failures += 1
        traceback.print_exc()

    if record["longform_id"] or record["short_id"]:
        lf_meta_d = json.loads((final_dir / "longform_meta.json").read_text())
        new_refs = lf_meta_d.get("verse_refs", [])
        total = _burn_ledger(new_refs)
        record["verse_refs"] = new_refs
        state["published"].append(record)
        save_state(state)
        print(f"State saved: episode {ep}, {len(new_refs)} verses burned (ledger: {total}).")
    if failures:
        sys.exit(1)

if __name__ == "__main__":
    force_day = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] not in ("-", "--no-upload") else None
    main(force_day, "--no-upload" not in sys.argv)

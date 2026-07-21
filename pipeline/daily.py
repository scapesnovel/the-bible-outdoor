#!/usr/bin/env python3
"""Daily orchestrator — stateful, idempotent, never repeats content.

- Picks the next unpublished (day, cycle) slot from data/state.json
- Builds long-form + Short + thumbnail
- Uploads as scheduled premieres at prime time for Tier-1 audiences:
    * Long-form -> 10:45 UTC  (= 6:45am New York morning devotional slot)
    * Short     -> 16:00 UTC  (= noon New York / evening Europe scroll time)
- Records video IDs in state.json (committed back by the workflow),
  so a re-run the same day is a safe no-op.
"""
import sys, os, json, pathlib, datetime, traceback
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import OUT, load_state, save_state, next_slot, load_plan, today_str, already_published_today
import verse_picker as vp

LONGFORM_UTC = (10, 45)
SHORT_UTC = (16, 0)

def publish_at(hh_mm):
    now = datetime.datetime.now(datetime.timezone.utc)
    t = now.replace(hour=hh_mm[0], minute=hh_mm[1], second=0, microsecond=0)
    if t <= now + datetime.timedelta(minutes=10):
        t += datetime.timedelta(days=1)
    return t.isoformat().replace("+00:00", "Z")

def main(force_day=None, do_upload=True):
    state = load_state()
    plan = load_plan()

    if do_upload and already_published_today(state):
        print(f"Already published today ({today_str()}). Nothing to do — safe exit.")
        return

    if force_day:
        day, cycle = force_day, 1
    else:
        day, cycle = next_slot(state, len(plan["days"]))

    entry = plan["days"][day - 1]
    ep = (cycle - 1) * len(plan["days"]) + day
    print(f"=== The Bible Outdoor — Episode {ep} (day {day}, cycle {cycle}): {entry['theme']} ===")

    import build_longform, build_short, build_thumbnail
    lf_path, lf_meta = build_longform.build(day, cycle)
    sh_path, sh_meta = build_short.build(day, cycle)
    thumb = build_thumbnail.build(day)

    if not do_upload:
        print("Build-only mode; skipping upload.")
        return

    import upload
    final_dir = OUT / f"day{day:02d}"
    record = {"date": today_str(), "day": day, "cycle": cycle, "episode": ep,
              "theme": entry["theme"], "longform_id": None, "short_id": None}
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
        # Verses used in this episode are burned into the permanent ledger
        # so they are NEVER picked again.
        lf_meta_d = json.loads((final_dir / "longform_meta.json").read_text())
        used = vp.load_ledger()
        new_refs = lf_meta_d.get("verse_refs", [])
        used.update(new_refs)
        vp.save_ledger(used)
        record["verse_refs"] = new_refs
        state["published"].append(record)
        save_state(state)
        print(f"State saved: episode {ep} recorded, {len(new_refs)} verses added to never-repeat ledger ({len(used)} total).")
    if failures:
        sys.exit(1)

if __name__ == "__main__":
    force_day = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] not in ("-", "--no-upload") else None
    main(force_day, "--no-upload" not in sys.argv)

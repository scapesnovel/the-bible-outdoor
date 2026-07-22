#!/usr/bin/env python3
"""Custom-Shorts queue orchestrator.

Runs in GitHub Actions whenever data/custom_queue.json changes (owner used
the phone app). For each queue item:

  status "pending"   -> validate, render via build_custom.py, upload as a
                        scheduled premiere at publish_at, mark "scheduled"
  status "cancelled" -> if already uploaded, delete the video from YouTube;
                        mark "removed"

Rules enforced server-side (the app enforces them client-side too):
  * max 2 Shorts per publish-date (customs + bot uploads combined)
  * >= MIN_GAP_HOURS between any two Shorts on the same date
  * >= MIN_LEAD_HOURS between now and publish_at (render + upload buffer)

Custom verse refs are NEVER burned to the no-repeat ledger — the owner's
explanation is personal, so the bot may feature the same verse again later.
"""
import sys, json, pathlib, datetime, traceback
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import DATA, load_state

QUEUE_PATH = DATA / "custom_queue.json"
MIN_GAP_HOURS = 4
MIN_LEAD_HOURS = 3
MAX_PER_DAY = 2

def load_queue():
    if QUEUE_PATH.exists():
        return json.loads(QUEUE_PATH.read_text())
    return {"queue": []}

def save_queue(q):
    QUEUE_PATH.write_text(json.dumps(q, indent=1))

def _dt(iso):
    return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))

def _date(iso):
    return _dt(iso).date().isoformat()

def bot_uploads_on(state, date_iso):
    """How many bot Shorts were published/scheduled for a given date."""
    n = 0
    for p in state.get("published", []):
        if p.get("date") == date_iso:
            n += len(p.get("short_ids") or ([p["short_id"]] if p.get("short_id") else []))
            if p.get("longform_id"):
                n += 0  # long-form doesn't count against the Shorts cap
    return n

def validate(item, queue, state):
    """Return None if OK else a human-readable rejection reason."""
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        t = _dt(item["publish_at"])
    except Exception:
        return "invalid publish_at"
    if t < now + datetime.timedelta(hours=MIN_LEAD_HOURS):
        return f"needs at least {MIN_LEAD_HOURS}h lead time for rendering"
    d = _date(item["publish_at"])
    same_day = [x for x in queue["queue"]
                if x["id"] != item["id"] and x.get("status") in ("pending", "scheduled")
                and _date(x["publish_at"]) == d]
    if len(same_day) + 1 + bot_uploads_on(state, d) > MAX_PER_DAY:
        return f"more than {MAX_PER_DAY} Shorts on {d}"
    for x in same_day:
        gap = abs((t - _dt(x["publish_at"])).total_seconds()) / 3600
        if gap < MIN_GAP_HOURS:
            return f"only {gap:.1f}h from another custom Short (min {MIN_GAP_HOURS}h)"
    if not (item.get("text") or "").strip():
        return "empty verse text"
    if len((item.get("explanation") or "").strip()) < 20:
        return "explanation too short (min 20 chars)"
    return None

def main(do_upload=True):
    q = load_queue()
    state = load_state()
    changed = False
    failures = 0

    for item in q["queue"]:
        st = item.get("status")

        if st == "cancelled":
            vid = item.get("video_id")
            if vid and do_upload:
                try:
                    import upload
                    upload.yt_client().videos().delete(id=vid).execute()
                    print(f"CANCELLED + deleted from YouTube: {item['id']} ({vid})")
                except Exception:
                    traceback.print_exc()
                    print(f"  (video {vid} could not be deleted — may already be gone)")
            else:
                print(f"CANCELLED before upload: {item['id']}")
            item["status"] = "removed"
            changed = True
            continue

        if st != "pending":
            continue

        reason = validate(item, q, state)
        if reason:
            print(f"REJECTED {item['id']}: {reason}")
            item["status"] = "rejected"
            item["reason"] = reason
            changed = True
            continue

        try:
            import build_custom
            final, meta_path = build_custom.build(item)
            if do_upload:
                import upload
                vid = upload.upload(meta_path, None, publish_at_iso=item["publish_at"])
                item["video_id"] = vid
            item["status"] = "scheduled" if do_upload else "rendered"
            changed = True
            print(f"SCHEDULED custom Short {item['id']} -> {item['publish_at']}")
        except Exception:
            failures += 1
            traceback.print_exc()

    # prune items whose lifecycle finished > 30 days ago to keep the file small
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=30))
    before = len(q["queue"])
    q["queue"] = [x for x in q["queue"]
                  if not (x.get("status") in ("removed", "rejected")
                          and _dt(x["publish_at"]) < cutoff)]
    if len(q["queue"]) != before:
        changed = True

    if changed:
        save_queue(q)
        print("queue saved.")
    if failures:
        sys.exit(1)

if __name__ == "__main__":
    main("--no-upload" not in sys.argv)

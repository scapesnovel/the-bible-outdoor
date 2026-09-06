#!/usr/bin/env python3
"""Custom-Shorts queue orchestrator.

Runs in GitHub Actions whenever data/custom_queue.json changes (owner used
the phone app). For each queue item:

  status "pending"   -> validate, render via build_custom.py, upload as a
                        scheduled premiere at publish_at, mark "scheduled"
  status "cancelled" -> if still UNPUBLISHED, delete the video from YouTube
                        and mark "removed". If the premiere time has already
                        passed, the video is LIVE — never delete it; flip the
                        item to "published" instead (deleting live videos
                        looks like metric gaming and loses real views).
  status "scheduled" -> once publish_at passes, flip to "published" so the
                        app's queue only shows genuinely upcoming Shorts.

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
MAX_UPCOMING = 6           # max not-yet-live custom Shorts in the pipeline at once

# ---- Monetization guard (YouTube "inauthentic/repetitious content" policy) ----
MAX_VERSE_POSTS = 2        # a verse may appear at most this many times on the channel
MIN_REPEAT_GAP_DAYS = 30   # a repeat must be at least this many days from the previous post
MAX_EXPL_SIMILARITY = 0.6  # repeat explanations must be substantially different

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

def norm_ref(r):
    r = (r or "").strip()
    if r.startswith("Psalm "):
        r = "Psalms " + r[6:]
    return r

def expand_refs(display_ref):
    """'1 Peter 4:14-15' -> ['1 Peter 4:14', '1 Peter 4:15']."""
    import re
    r = norm_ref(display_ref)
    m = re.match(r"^(.+?)\s+(\d+):(\d+)(?:-(\d+))?$", r)
    if not m:
        return [r] if r else []
    book, ch = m.group(1), m.group(2)
    v1, v2 = int(m.group(3)), int(m.group(4) or m.group(3))
    return [f"{book} {ch}:{v}" for v in range(v1, min(v2, v1 + 30) + 1)]

def _verse_usage(queue, state, exclude_id=None):
    """ref -> list of {'date','explanation'} for every live/planned post."""
    uses = {}
    for p in state.get("published", []):
        for ref in (p.get("verse_refs") or []):
            uses.setdefault(norm_ref(ref), []).append(
                {"date": p.get("date"), "explanation": None})
    for x in queue.get("queue", []):
        if x["id"] == exclude_id:
            continue
        if x.get("status") not in ("pending", "scheduled", "rendered", "published"):
            continue
        d = _date(x["publish_at"])
        for ref in expand_refs(x.get("display_ref", "")):
            uses.setdefault(ref, []).append(
                {"date": d, "explanation": x.get("explanation") or ""})
    return uses

def _similarity(a, b):
    import re
    ta = set(re.findall(r"[a-z']+", (a or "").lower()))
    tb = set(re.findall(r"[a-z']+", (b or "").lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)

def _day_is_free(queue, state, item, t):
    """Would publishing item at t violate the day cap or gaps?"""
    d = t.date().isoformat()
    same_day = [x for x in queue["queue"]
                if x["id"] != item["id"] and x.get("status") in ("pending", "scheduled", "rendered", "published")
                and _date(x["publish_at"]) == d]
    if len(same_day) + 1 + bot_uploads_on(state, d) > MAX_PER_DAY:
        return False
    for x in same_day:
        if abs((t - _dt(x["publish_at"])).total_seconds()) / 3600 < MIN_GAP_HOURS:
            return False
    return True

def reschedule_if_stale(item, queue, state):
    """If a pending item's publish_at slipped into the past (e.g. the
    pipeline was down for days), pick the next valid time instead of
    silently rejecting the owner's Short. Preserves the original
    time-of-day when possible."""
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        t = _dt(item["publish_at"])
    except Exception:
        return False
    if t >= now + datetime.timedelta(hours=MIN_LEAD_HOURS):
        return False  # still fine
    original = item["publish_at"]
    # Candidate 1..7: same wall-clock time on the next days
    cand = []
    for d in range(0, 8):
        c = (now + datetime.timedelta(days=d)).replace(
            hour=t.hour, minute=t.minute, second=0, microsecond=0)
        cand.append(c)
    # Candidate fallback: ASAP with lead buffer
    cand.append((now + datetime.timedelta(hours=MIN_LEAD_HOURS, minutes=20)
                 ).replace(second=0, microsecond=0))
    for c in sorted(cand):
        if c < now + datetime.timedelta(hours=MIN_LEAD_HOURS):
            continue
        if _day_is_free(queue, state, item, c):
            item["publish_at"] = c.isoformat().replace("+00:00", "Z")
            item["rescheduled_from"] = original
            print(f"RESCHEDULED stale custom Short {item['id']}: "
                  f"{original} -> {item['publish_at']}")
            return True
    return False

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
                if x["id"] != item["id"] and x.get("status") in ("pending", "scheduled", "rendered", "published")
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
    upcoming = [x for x in queue["queue"]
                if x["id"] != item["id"]
                and x.get("status") in ("pending", "scheduled", "rendered")
                and _dt(x["publish_at"]) > now]
    if len(upcoming) >= MAX_UPCOMING:
        return (f"pipeline full — {MAX_UPCOMING} custom Shorts already waiting to "
                f"premiere; let some go live first")

    # ---- Monetization guard: limited repeats, spaced out, fresh explanations ----
    uses = _verse_usage(queue, state, exclude_id=item["id"])
    for ref in expand_refs(item.get("display_ref", "")):
        prior = uses.get(ref, [])
        if len(prior) + 1 > MAX_VERSE_POSTS:
            return (f"{ref} already posted {len(prior)}x — channel limit is "
                    f"{MAX_VERSE_POSTS} posts per verse (protects monetization)")
        if prior:
            gaps = [abs((t.date() - datetime.date.fromisoformat(p["date"])).days)
                    for p in prior if p.get("date")]
            if gaps and min(gaps) < MIN_REPEAT_GAP_DAYS:
                return (f"{ref} was posted {min(gaps)} day(s) from this slot — "
                        f"repeats must be >= {MIN_REPEAT_GAP_DAYS} days apart")
            for p in prior:
                if p.get("explanation") is not None:
                    sim = _similarity(item.get("explanation", ""), p["explanation"])
                    if sim > MAX_EXPL_SIMILARITY:
                        return (f"explanation is {int(sim*100)}% similar to the previous "
                                f"post of {ref} — a repeat needs a fresh reflection")
    return None

def main(do_upload=True):
    q = load_queue()
    state = load_state()
    changed = False
    failures = 0

    if do_upload and any(x.get("status") in ("pending", "cancelled")
                         for x in q["queue"]):
        import upload
        upload.check_token()  # fail fast BEFORE spending 30 min rendering

    now = datetime.datetime.now(datetime.timezone.utc)
    for item in q["queue"]:
        st = item.get("status")

        # Lifecycle: a scheduled premiere whose time has passed is LIVE.
        if st == "scheduled" and _dt(item["publish_at"]) <= now:
            item["status"] = "published"
            changed = True
            print(f"PUBLISHED (premiere time passed): {item['id']} ({item.get('video_id','')})")
            continue

        if st == "cancelled":
            vid = item.get("video_id")
            went_live = vid and _dt(item["publish_at"]) <= now
            if went_live:
                # SAFETY: the premiere already happened — this is a LIVE video
                # with real views. Never delete it; undo the cancel.
                item["status"] = "published"
                item["reason"] = ("Cancel ignored — this Short already premiered and "
                                  "is live on the channel. Live videos are never "
                                  "auto-deleted (protects views + channel standing).")
                changed = True
                print(f"CANCEL REFUSED (already live): {item['id']} ({vid})")
                continue
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

        if reschedule_if_stale(item, q, state):
            changed = True
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
                try:  # cross-post (Facebook Reels + Pinterest) — never fatal
                    import crosspost
                    meta_d = json.loads(pathlib.Path(meta_path).read_text())
                    crosspost.crosspost(meta_d["file"], meta_d, vid)
                except Exception:
                    traceback.print_exc()
            item["status"] = "scheduled" if do_upload else "rendered"
            changed = True
            print(f"SCHEDULED custom Short {item['id']} -> {item['publish_at']}")
            # Monetization guard: once a verse hits the channel-wide limit,
            # burn it into the bot ledger so the bot never re-picks it.
            try:
                import verse_picker as vp
                uses = _verse_usage(q, state)
                ledger = vp.load_ledger()
                burn = {r for r in expand_refs(item.get("display_ref", ""))
                        if len(uses.get(r, [])) >= MAX_VERSE_POSTS and r not in ledger}
                if burn:
                    ledger.update(burn)
                    vp.save_ledger(ledger)
                    print(f"ledger: burned {sorted(burn)} (verse post-limit reached)")
            except Exception:
                traceback.print_exc()
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

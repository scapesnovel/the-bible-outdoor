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

SCHEDULING GUARANTEE (collision-proof):
- Publish times are chosen by a YouTube-aware allocator: before anything
  is scheduled, the bot reads the channel's real upcoming scheduled
  videos and everything published in the last 24h, and keeps a hard
  >= MIN_GAP_HOURS gap from ALL of them, from every owner custom Short,
  and from its own picks within the same run.
- A missed prime slot is NEVER rolled to the next day (that caused the
  Jul-25 double-publish). If today's prime slots are gone, the Short is
  scheduled shortly after generation instead, stepped past any conflict.
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

GAP_H = custom_mod.MIN_GAP_HOURS      # hard gap between any two publishes
LEAD_MIN = 20                         # min minutes between "now" and a publish
# Preferred same-day slots, in order of audience value.
PREF_SLOTS = [(13, 0), (22, 0), (16, 0), (18, 0), (20, 0), (11, 0)]


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(t):
    return t.isoformat().replace("+00:00", "Z")


def _parse_iso(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def publish_at(hh_mm):
    """Same-day-only publish time. If the slot already passed, publish
    soon after generation instead of rolling to the next day (the old
    +1 day rollover collided with the next day's run)."""
    now = _utcnow()
    t = now.replace(hour=hh_mm[0], minute=hh_mm[1], second=0, microsecond=0)
    if t <= now + datetime.timedelta(minutes=LEAD_MIN):
        t = now + datetime.timedelta(minutes=LEAD_MIN + 10)
        t = t.replace(second=0, microsecond=0)
    return _iso(t)


def _youtube_occupied(yt):
    """Real publish times already taken on the channel: every future
    scheduled video (publishAt) + everything published in the last 24h."""
    occ = []
    try:
        ch = yt.channels().list(part="contentDetails", mine=True).execute()
        uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        items = yt.playlistItems().list(part="contentDetails",
                                        playlistId=uploads, maxResults=20).execute()
        ids = [i["contentDetails"]["videoId"] for i in items.get("items", [])]
        if ids:
            vids = yt.videos().list(part="status,snippet", id=",".join(ids)).execute()
            cutoff = _utcnow() - datetime.timedelta(hours=24)
            for v in vids.get("items", []):
                ts = (v.get("status", {}).get("publishAt")
                      or v.get("snippet", {}).get("publishedAt"))
                if not ts:
                    continue
                try:
                    t = _parse_iso(ts)
                except Exception:
                    continue
                if t > cutoff:
                    occ.append(t)
        print(f"Schedule check: {len(occ)} occupied time(s) on channel "
              f"(scheduled or published <24h).")
    except Exception:
        traceback.print_exc()
        print("WARN: could not read channel schedule from YouTube; "
              "using local state/queue times only.")
    return occ


def _queue_occupied():
    """All pending/scheduled owner custom Shorts (any date)."""
    occ = []
    q = custom_mod.load_queue()
    for x in q.get("queue", []):
        if x.get("status") in ("pending", "scheduled"):
            try:
                occ.append(_parse_iso(x["publish_at"]))
            except Exception:
                continue
    return occ


def _state_occupied(state):
    """Publish times recorded in recent state entries (belt & braces in
    case the YouTube read fails)."""
    occ = []
    cutoff = _utcnow() - datetime.timedelta(hours=48)
    for rec in state.get("published", [])[-6:]:
        for ts in rec.get("publish_times", []):
            try:
                t = _parse_iso(ts)
            except Exception:
                continue
            if t > cutoff:
                occ.append(t)
    return occ


def allocate_publish_times(n, occupied):
    """Pick n publish datetimes. Prefer today's prime slots; every pick
    keeps >= GAP_H hours from every occupied time and from each other.
    If no clean slot remains today, publish shortly after generation
    (stepped past conflicts) — never a blind next-day rollover."""
    now = _utcnow()
    earliest = now + datetime.timedelta(minutes=LEAD_MIN)
    chosen = []

    def clear(t):
        for o in list(occupied) + chosen:
            if abs((t - o).total_seconds()) < GAP_H * 3600:
                return False
        return True

    for _ in range(n):
        pick = None
        for hh, mm in PREF_SLOTS:
            t = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if t >= earliest and clear(t):
                pick = t
                break
        if pick is None:
            # ASAP after generation, stepping past any conflicting window.
            t = (earliest + datetime.timedelta(minutes=10)).replace(second=0, microsecond=0)
            for _guard in range(50):
                conflicts = [o for o in list(occupied) + chosen
                             if abs((t - o).total_seconds()) < GAP_H * 3600]
                if not conflicts:
                    break
                t = max(conflicts) + datetime.timedelta(hours=GAP_H, minutes=5)
            pick = t
        chosen.append(pick)

    chosen.sort()
    return chosen


def _customs_today():
    """Owner-scheduled custom Shorts whose publish date is today (UTC).
    Returns their publish datetimes."""
    q = custom_mod.load_queue()
    out = []
    for x in q.get("queue", []):
        if x.get("status") in ("pending", "scheduled"):
            try:
                t = _parse_iso(x["publish_at"])
            except Exception:
                continue
            if t.date().isoformat() == today_str():
                out.append(t)
    return out


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

        # Collision-proof allocation: consult the channel's REAL schedule.
        occupied = _queue_occupied() + _state_occupied(state)
        try:
            occupied += _youtube_occupied(upload.yt_client())
        except Exception:
            traceback.print_exc()
            print("WARN: YouTube client unavailable for schedule check.")
        times = allocate_publish_times(n, occupied)
        print("Publish plan: " + ", ".join(_iso(t) for t in times))

        record = {"date": today_str(), "day": day, "cycle": cycle, "episode": ep,
                  "theme": entry["theme"], "mode": "shorts", "short_ids": [],
                  "verse_refs": [], "publish_times": []}
        failures = 0
        for i, (path, meta) in enumerate(built):
            suffix = "" if i == 0 else f"_{chr(ord('a') + i)}"
            iso = _iso(times[i % len(times)])
            try:
                vid = upload.upload(final_dir / f"short{suffix}_meta.json", None,
                                    publish_at_iso=iso)
                record["short_ids"].append(vid)
                record["verse_refs"] += meta["verse_refs"]
                record["publish_times"].append(iso)
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

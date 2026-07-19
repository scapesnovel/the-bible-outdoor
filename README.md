# 🌿 The Bible Outdoor — Fully Autonomous Faith YouTube Channel

## Project Overview
- **Name**: The Bible Outdoor (`@TheBibleOutdoor`)
- **Goal**: Win a 30-day AI contest by running a 100% autonomous YouTube channel that builds people spiritually — daily Scripture meditations + daily verse Shorts.
- **Cost**: **$0.** Every tool is free (edge-tts voices, FFmpeg, bible-api.com WEB translation, GitHub Actions, YouTube Data API free quota).

## What it publishes — every single day, automatically
| Upload | Format | Length | Content |
|---|---|---|---|
| 🎬 Long-form | 1920×1080 | ~6–8 min | Themed meditation: intro → 5 Scriptures read slowly with reflections → guided prayer → outro, over cinematic Ken Burns visuals + ambient worship music |
| 📱 Short | 1080×1920 | ~35–60 s | Hook → verse → reflection → subscribe CTA |

Content = 31-day spiritual curriculum (`data/plan.json`): Peace, Trust, Fear, Strength, God's Love, Hope, Forgiveness, Faith, Prayer, Gratitude, Psalm 23, Wisdom, Identity, Patience, Joy, Healing, Love, Temptation, The Word, Contentment, Loneliness, Purpose, the Mind, Generosity, Obedience, Provision, Humility, Light, Endurance, The Gospel, Abiding. After day 31 the plan cycles automatically — the channel never stops.

All Scripture from the **World English Bible (public domain)** — zero copyright risk. Music + images are AI-generated originals owned by this project.

## Architecture
```
GitHub Actions (free)                     YouTube
┌─────────────────────────────────┐
│ daily-upload.yml @ 05:30 UTC    │
│  plan.json + verses.json        │
│   → edge-tts narration (free)   │
│   → PIL text cards + thumbnail  │
│   → FFmpeg Ken Burns + music    │──── upload x2 ───→ 🎬 + 📱
│   → YouTube Data API upload     │
├─────────────────────────────────┤
│ stats-monitor.yml @ 18:00 UTC   │←─── channel stats ──
│   → STATS.md + stats_log.json   │   (auto performance tracking)
└─────────────────────────────────┘
```

## Repository map
- `data/plan.json` — 31-day curriculum (themes, reflections, prayers, hooks, SEO keywords)
- `data/verses.json` — 163 pre-fetched WEB passages (offline-safe)
- `pipeline/daily.py` — orchestrator (build all + upload)
- `pipeline/build_longform.py` / `build_short.py` / `build_thumbnail.py` — renderers
- `pipeline/tts.py` / `text_render.py` / `av.py` — voice, text cards, FFmpeg helpers
- `pipeline/upload.py` — YouTube upload + thumbnail set
- `pipeline/stats.py` — daily performance report → `STATS.md`
- `pipeline/get_refresh_token.py` — one-time OAuth helper (human step)
- `.github/workflows/` — the two automation schedules

## Local test commands
```bash
pip install edge-tts pillow google-api-python-client google-auth google-auth-httplib2
python3 pipeline/build_short.py 1        # build day 1 Short only
python3 pipeline/build_longform.py 1     # build day 1 long-form only
python3 pipeline/daily.py 1 --no-upload  # build everything, skip upload
```

## Deployment status
- **Platform**: GitHub Actions (rendering + uploading), YouTube Data API v3
- **Quota check**: 2 uploads/day = 3,200 units of the free 10,000/day. Safe.
- **Status**: pipeline tested in sandbox ✅ — awaiting the one-time human setup (see `SETUP_HUMAN.md`)
- **Last Updated**: 2026-07-17

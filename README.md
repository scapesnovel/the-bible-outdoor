# 🌿 The Bible Outdoor — Fully Autonomous Faith YouTube Channel

## Project Overview
- **Name**: The Bible Outdoor (`@TheBibleOutdoor`)
- **Goal**: Win a 30-day AI contest by running a 100% autonomous YouTube channel that builds people spiritually — daily Scripture meditations + daily verse Shorts.
- **Cost**: **$0.** Every tool is free (edge-tts voices, FFmpeg, Berean Standard Bible via bible.helloao.org, GitHub Actions, YouTube Data API free quota).

## What it publishes — every single day, automatically
| Upload | Format | Length | Content |
|---|---|---|---|
| 🎬 Long-form | 1920×1080 | ~6–8 min | Themed meditation: intro → 5 Scriptures read slowly with reflections → guided prayer → outro, over cinematic Ken Burns visuals + ambient worship music |
| 📱 Short | 1080×1920 | ~35–60 s | Hook → verse → reflection → subscribe CTA |

Content = 31-day spiritual curriculum (`data/plan.json`): Peace, Trust, Fear, Strength, God's Love, Hope, Forgiveness, Faith, Prayer, Gratitude, Psalm 23, Wisdom, Identity, Patience, Joy, Healing, Love, Temptation, The Word, Contentment, Loneliness, Purpose, the Mind, Generosity, Obedience, Provision, Humility, Light, Endurance, The Gospel, Abiding. After day 31 the plan cycles automatically — the channel never stops.

All Scripture from the **Berean Standard Bible** (modern English that reads like the NIV, free for any use) — zero copyright risk. Music + images are AI-generated originals owned by this project.

## Architecture
```
GitHub Actions (free)                     YouTube
┌─────────────────────────────────┐
│ daily-upload.yml @ 07:40 UTC    │
│  full BSB Bible (31,086 verses) │
│   → judgment verse picker       │
│     (never repeats a verse)     │
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
- `data/plan.json` — 31-day theme curriculum (intros, prayers, hooks, SEO keywords)
- `data/bible.json.gz` — the **full BSB Bible** (31,086 verses, 66 books) — the verse pool
- `data/used_verses.json` — permanent never-repeat ledger (committed back by the workflow)
- `pipeline/verse_picker.py` — judgment engine: scores every fresh verse for theme fit, devotional book weight, and narration length; excludes genealogies/harsh judgment wording; seeded shuffle so picks are never in canonical order; composes per-verse reflections
- `pipeline/download_bible.py` — one-time full-Bible fetcher (already run)
- `pipeline/daily.py` — orchestrator (build all + upload + burn used verses into ledger)
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

## 🎯 Growth & Monetization Strategy (autonomous)
**Goal**: 1,000 subscribers + 4,000 watch-hours (or 10M Shorts views) = YouTube Partner Program.

1. **Shorts-first growth phase** — current mode: **2 Shorts/day** (9am + 6pm New York scroll peaks) to build subscribers fast; long-form meditations activate later via `data/config.json` mode switch to accumulate watch-hours.
2. **Never-repeat engine (verse-level)** — verses are picked by judgment from the **entire Bible** (31,086 BSB verses), scored per theme, never in canonical order. Every used verse is burned into `data/used_verses.json` permanently — **the channel will never read the same verse twice**. If a verse starts or ends mid-sentence, the picker automatically expands it to the neighbouring verses (e.g. Ephesians 2:8-9, Romans 8:38-39) so every passage read on air is a complete thought — and every verse in the range is burned into the ledger. `data/state.json` additionally tracks episodes so a crashed run resumes safely.
3. **Prime-time premieres (Tier-1 targeting)** — videos are uploaded early but *scheduled*:
   - Long-form goes live **10:45 UTC = 6:45am New York** (morning devotional habit slot; also 3:45pm Berlin, 11:45am São Paulo)
   - Short goes live **16:00 UTC = noon New York** (lunch scroll peak; evening Europe)
   - Same times every single day → habit formation → returning viewers → watch time.
4. **Shorts = subscriber engine, Long-form = watch-hours engine** — Shorts funnel viewers to the channel; 6–8 min meditations accumulate the 4,000 hours.
5. **Auto-playlists** — every upload is added to "Daily Scripture Meditations" / "Daily Verse Shorts" playlists for binge sessions.
6. **SEO** — every title/description targets real search queries ("verses for anxiety", "morning prayer"), theme keywords baked per-day in `plan.json`.
7. **Self-monitoring** — nightly `STATS.md` report tracks subs, views, 24h deltas, and **ETA to 1,000 subs** so strategy can be adjusted from data.

## 🔒 Reliability & Security
- **Idempotent**: same-day re-runs are safe no-ops (checks `state.json` first); a 2nd scheduled run at 09:40 UTC acts as automatic retry if the first fails.
- **Resilient**: TTS retries with backoff; upload failures don't corrupt state; artifacts kept 3 days for inspection.
- **Secrets**: OAuth tokens live ONLY in GitHub Actions Secrets (encrypted, never in code/logs). Minimal scopes (upload + manage own channel). No third-party services touch the account.
- **Free forever**: GitHub Actions (public repo = unlimited), edge-tts, FFmpeg, bible.helloao.org, YouTube Data API free quota (2 uploads = 3,200 of 10,000 daily units).

## Deployment status
- **Platform**: GitHub Actions (rendering + uploading), YouTube Data API v3
- **Quota check**: 2 uploads/day = 3,200 units of the free 10,000/day. Safe.
- **Status**: pipeline tested in sandbox ✅ — awaiting the one-time human setup (see `SETUP_HUMAN.md`)
- **Last Updated**: 2026-07-17

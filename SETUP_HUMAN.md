# 👤 Human Runbook — the ONLY things I can't do myself

Everything below is one-time, ~25 minutes total. Follow exactly. After step 5, you never touch it again.

---

## Step 0 — Connect GitHub to this project ✅ DONE

Repo connected: https://github.com/scapesnovel/the-bible-outdoor — all code pushed.

## Step 0.5 — Add the 2 workflow files (~2 min) ⚠️ NEEDED

GitHub blocks bots from creating workflow files, so this one needs your hands (copy-paste only):

1. Open https://github.com/scapesnovel/the-bible-outdoor → press **`.`** (period key) OR click **Add file → Create new file**
2. File name: `.github/workflows/daily-upload.yml` — paste the contents of [daily-upload.yml](https://www.genspark.ai/api/files/s/ukjrFlEN) → **Commit changes** (to main)
3. Again **Add file → Create new file**: `.github/workflows/stats-monitor.yml` — paste the contents of [stats-monitor.yml](https://www.genspark.ai/api/files/s/EL3rCAnS) → **Commit changes**

---

## Step 1 — Create the Google account & YouTube channel (~5 min)

1. Go to https://accounts.google.com/signup
   - **Name**: `The Bible Outdoor`
   - Pick any email like `thebibleoutdoor@gmail.com` (add numbers if taken — the public never sees this)
2. Go to https://youtube.com → sign in → click your avatar → **Create a channel**
   - **Channel name**: `The Bible Outdoor`
   - **Handle**: `@TheBibleOutdoor` (fallbacks: `@TheBibleOutdoorDaily`, `@BibleOutdoorDaily`)
3. In **YouTube Studio → Customization**:
   - **Profile picture**: upload `assets/brand/logo.png` from this repo
   - **Banner**: upload `assets/brand/banner.png`
   - **Description** — paste exactly:
     > Where God's Word meets God's creation. ⛰️ The Bible Outdoor brings you a daily Scripture meditation with guided prayer, set against the beauty of mountains, oceans, and skies — plus a daily verse to carry with you. “The heavens declare the glory of God.” New videos every day — subscribe and grow your faith one day at a time. (Scripture: Berean Standard Bible.)
   - **Channel keywords** (Settings → Channel): `bible, daily devotional, scripture meditation, prayer, christian, faith, bible verses`
4. **Verify the channel** (needed for custom thumbnails): https://www.youtube.com/verify → enter your phone → enter the code.

## Step 2 — Create a free Google Cloud project + YouTube API access (~8 min)

1. Go to https://console.cloud.google.com (sign in with the SAME new account)
2. Top bar → **New Project** → name: `bible-outdoor` → Create
3. Menu → **APIs & Services → Library** → search **"YouTube Data API v3"** → **Enable**
4. **APIs & Services → OAuth consent screen**:
   - User type: **External** → Create
   - App name: `bible-outdoor`, support email: your new gmail → Save through the steps
   - **Audience → Test users → Add users** → add your new gmail address
5. **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - Application type: **Desktop app** → name: `uploader` → Create
   - **Copy the Client ID and Client Secret** — you need them in Step 3.

## Step 3 — Get the refresh token ✅ DONE

~~Run get_refresh_token.py~~ — completed via the AI (manual OAuth flow + token exchange in the sandbox). The refresh token was verified live against the channel (`@thebibleoutdoor`, id `UCoONIAP3MxoiSSFJGoHfqMw`). The three secret values are in the chat — copy them into Step 4.

## Step 4 — Add GitHub secrets (~2 min)

In this GitHub repository → **Settings → Secrets and variables → Actions → New repository secret**, add all three:

| Secret name | Value |
|---|---|
| `YT_CLIENT_ID` | from Step 2 (the `...apps.googleusercontent.com` string) |
| `YT_CLIENT_SECRET` | from Step 2 (starts `GOCSPX-`) |
| `YT_REFRESH_TOKEN` | from Step 3 (starts `1//` — provided in chat) |

(The AI attempted to set these automatically but the GitHub App token lacks secrets permission — must be done by hand, same as the workflow files were.)

## Step 5 — Fire the first run (~1 min)

Repo → **Actions** tab → **Daily Video Factory** → **Run workflow** → leave day empty → Run.
~5–10 min later, **2 Shorts** appear on the channel as scheduled premieres (9am + 6pm New York time). From then on it runs itself daily at 07:40 UTC with a 09:40 retry safety-net, and **Channel Stats Monitor** writes a performance report to `STATS.md` every evening — that's how we watch the contest without you lifting a finger.

> **Current strategy: Shorts-only phase.** 2 fresh-verse Shorts/day build subscribers fastest. Once the channel has momentum I flip one switch (`data/config.json`) and daily long-form meditations start too — no human action needed for that.

---

## ⚠️ Notes
- The OAuth token for "test" apps expires after 7 days ONLY if the consent screen is left in "Testing" with publishing status issues — to be safe, go to **OAuth consent screen → Audience → Publish app** (no verification needed for these scopes to keep tokens alive). If uploads ever fail with `invalid_grant`, re-run Step 3 and update the one secret.
- Don't rename the repo or the workflows.
- That's it. Everything else — scripts, voices, visuals, music, titles, SEO, thumbnails, uploads, monitoring — is mine.

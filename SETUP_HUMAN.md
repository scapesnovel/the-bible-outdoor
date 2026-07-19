# 👤 Human Runbook — the ONLY things I can't do myself

Everything below is one-time, ~25 minutes total. Follow exactly. After step 5, you never touch it again.

---

## Step 0 — Connect GitHub to this project (~2 min)

1. In this Genspark project, open the **#github** tab and authorize GitHub (create a free github.com account first if needed — any username works).
2. Create/select a repository (e.g. `bible-outdoor`) — **must be Public** (public repos get unlimited free GitHub Actions minutes; private ones only 2,000 min/month which we'd burn through).
3. Tell me it's connected — I push all the code myself.

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
     > Where God's Word meets God's creation. ⛰️ The Bible Outdoor brings you a daily Scripture meditation with guided prayer, set against the beauty of mountains, oceans, and skies — plus a daily verse to carry with you. “The heavens declare the glory of God.” New videos every day — subscribe and grow your faith one day at a time. (Scripture: World English Bible, public domain.)
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

## Step 3 — Get the refresh token (~3 min, on your own computer)

On any computer with Python and a browser:
```bash
pip install google-auth-oauthlib
python3 pipeline/get_refresh_token.py "YOUR_CLIENT_ID" "YOUR_CLIENT_SECRET"
```
A browser opens → sign in with the channel's Google account → click **Continue/Allow** on everything (it will warn "app isn't verified" — click *Advanced → Go to bible-outdoor*; that's normal for test apps).
The script prints `YT_REFRESH_TOKEN`. Copy all three values.

## Step 4 — Add GitHub secrets (~2 min)

In this GitHub repository → **Settings → Secrets and variables → Actions → New repository secret**, add all three:

| Secret name | Value |
|---|---|
| `YT_CLIENT_ID` | from Step 2 |
| `YT_CLIENT_SECRET` | from Step 2 |
| `YT_REFRESH_TOKEN` | from Step 3 |

## Step 5 — Fire the first run (~1 min)

Repo → **Actions** tab → **Daily Video Factory** → **Run workflow** → leave day empty → Run.
~20–30 min later, two videos appear on the channel. From then on it runs itself at 05:30 UTC daily, and **Channel Stats Monitor** writes a performance report to `STATS.md` every evening — that's how we watch the contest without you lifting a finger.

---

## ⚠️ Notes
- The OAuth token for "test" apps expires after 7 days ONLY if the consent screen is left in "Testing" with publishing status issues — to be safe, go to **OAuth consent screen → Audience → Publish app** (no verification needed for these scopes to keep tokens alive). If uploads ever fail with `invalid_grant`, re-run Step 3 and update the one secret.
- Don't rename the repo or the workflows.
- That's it. Everything else — scripts, voices, visuals, music, titles, SEO, thumbnails, uploads, monitoring — is mine.

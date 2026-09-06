#!/usr/bin/env python3
"""Cross-posting: Facebook Reels + Pinterest pins for every Short.

Design rules (same philosophy as the rest of the engine):
  * 100% free tiers — Meta Graph API and Pinterest API cost nothing.
  * OPTIONAL and NON-FATAL: if a platform's secrets are missing or a call
    fails, we log and move on. YouTube is the primary channel; cross-posting
    must never break the daily run.
  * Every cross-post links BACK to the YouTube channel — each platform
    becomes a discovery funnel for the main channel.

Secrets (GitHub Actions):
  Facebook : FB_PAGE_ID, FB_APP_ID, FB_APP_SECRET  (never expire)
             — the Page token itself lives in data/fb_token.json and is
               auto-refreshed on every run (60-day tokens, renewed 2x/day,
               so it never actually expires).
  Pinterest: PIN_APP_ID, PIN_APP_SECRET,
             PIN_REFRESH_TOKEN, PIN_BOARD_ID    (refresh flow like YouTube)
"""
import os, json, base64, subprocess, pathlib, traceback
import urllib.request, urllib.parse

YT_CHANNEL_URL = "https://www.youtube.com/@thebibleoutdoor"
GRAPH = "https://graph.facebook.com/v21.0"
PIN_API = "https://api.pinterest.com/v5"
ROOT = pathlib.Path(__file__).resolve().parent.parent
FB_TOKEN_FILE = ROOT / "data" / "fb_token.json"


def _http(url, data=None, headers=None, method=None, raw=False):
    if isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {},
                                 method=method or ("POST" if data else "GET"))
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
    return body if raw else json.loads(body or b"{}")


# ---------------------------------------------------------------------------
# Facebook Reels
# ---------------------------------------------------------------------------
def _fb_page_token():
    """Return a valid Page token, self-refreshing it in data/fb_token.json.

    Facebook long-lived Page tokens expire after ~60 days, but they can be
    re-exchanged (fb_exchange_token) for a fresh 60-day token at any time
    using the app id + secret (which never expire). Since the engine runs
    twice a day, the token is perpetually renewed and never lapses.
    """
    # 1) explicit env token wins (also used for first bootstrap)
    env_tok = os.environ.get("FB_PAGE_TOKEN")
    app_id = os.environ.get("FB_APP_ID")
    app_secret = os.environ.get("FB_APP_SECRET")
    stored = {}
    if FB_TOKEN_FILE.exists():
        try:
            stored = json.loads(FB_TOKEN_FILE.read_text())
        except Exception:
            stored = {}
    token = stored.get("token") or env_tok
    if not token:
        return None
    # 2) refresh if we have app credentials (extends expiry another 60 days)
    if app_id and app_secret:
        try:
            j = _http(f"{GRAPH}/oauth/access_token?"
                      + urllib.parse.urlencode({
                          "grant_type": "fb_exchange_token",
                          "client_id": app_id,
                          "client_secret": app_secret,
                          "fb_exchange_token": token}))
            new_tok = j.get("access_token")
            if new_tok:
                token = new_tok
                FB_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
                FB_TOKEN_FILE.write_text(json.dumps({"token": token}))
                print("  crosspost: Facebook token refreshed (+60 days)")
        except Exception:
            print("  crosspost: Facebook token refresh failed — using current token")
    return token


def post_facebook_reel(video_path, description):
    page_id = os.environ.get("FB_PAGE_ID")
    token = _fb_page_token()
    if not (page_id and token):
        print("  crosspost: Facebook secrets not set — skipping")
        return None
    video_path = pathlib.Path(video_path)
    size = video_path.stat().st_size
    # 1) start upload session
    j = _http(f"{GRAPH}/{page_id}/video_reels",
              data={"upload_phase": "start", "access_token": token})
    vid, upload_url = j["video_id"], j["upload_url"]
    # 2) upload the binary
    _http(upload_url, data=video_path.read_bytes(),
          headers={"Authorization": f"OAuth {token}",
                   "offset": "0", "file_size": str(size),
                   "Content-Type": "application/octet-stream"})
    # 3) finish + publish
    _http(f"{GRAPH}/{page_id}/video_reels",
          data={"upload_phase": "finish", "video_id": vid,
                "video_state": "PUBLISHED", "description": description,
                "access_token": token})
    print(f"  crosspost: Facebook Reel published ({vid})")
    return vid


# ---------------------------------------------------------------------------
# Pinterest
# ---------------------------------------------------------------------------
def _pin_access_token():
    app_id = os.environ.get("PIN_APP_ID")
    secret = os.environ.get("PIN_APP_SECRET")
    refresh = os.environ.get("PIN_REFRESH_TOKEN")
    if not (app_id and secret and refresh):
        return None
    basic = base64.b64encode(f"{app_id}:{secret}".encode()).decode()
    j = _http(f"{PIN_API}/oauth/token",
              data={"grant_type": "refresh_token", "refresh_token": refresh},
              headers={"Authorization": f"Basic {basic}",
                       "Content-Type": "application/x-www-form-urlencoded"})
    return j.get("access_token")


def _frame_jpeg(video_path, at_sec=2.0):
    """Grab one frame from the Short as the pin image (base64 jpeg)."""
    out = pathlib.Path(video_path).with_suffix(".pin.jpg")
    subprocess.run(["ffmpeg", "-y", "-ss", str(at_sec), "-i", str(video_path),
                    "-frames:v", "1", "-q:v", "3", str(out)],
                   check=True, capture_output=True)
    data = base64.b64encode(out.read_bytes()).decode()
    out.unlink(missing_ok=True)
    return data


def post_pinterest_pin(video_path, title, description, youtube_video_id):
    board = os.environ.get("PIN_BOARD_ID")
    token = _pin_access_token()
    if not (board and token):
        print("  crosspost: Pinterest secrets not set — skipping")
        return None
    link = f"https://www.youtube.com/watch?v={youtube_video_id}"
    body = json.dumps({
        "board_id": board,
        "title": title[:100],
        "description": (description[:750] + f"\n\nWatch: {link}")[:800],
        "link": link,
        "media_source": {"source_type": "image_base64",
                         "content_type": "image/jpeg",
                         "data": _frame_jpeg(video_path)},
    }).encode()
    j = _http(f"{PIN_API}/pins", data=body,
              headers={"Authorization": f"Bearer {token}",
                       "Content-Type": "application/json"})
    print(f"  crosspost: Pinterest pin created ({j.get('id')})")
    return j.get("id")


# ---------------------------------------------------------------------------
# Orchestrator — called after each successful YouTube upload
# ---------------------------------------------------------------------------
def crosspost(video_path, meta, youtube_video_id):
    """Non-fatal: post the Short to every configured platform."""
    results = {}
    ref = ", ".join(meta.get("verse_refs") or []) or meta.get("title", "")
    fb_desc = (f"{meta.get('description','').split(chr(10)+chr(10))[0]}\n\n"
               f"📺 Daily verses on YouTube: {YT_CHANNEL_URL}\n\n"
               f"#bible #dailyverse #faith #reels")
    try:
        results["facebook"] = post_facebook_reel(video_path, fb_desc)
    except Exception:
        traceback.print_exc()
        print("  crosspost: Facebook failed (non-fatal)")
    try:
        title = meta.get("title", "Daily Bible verse").replace("#shorts", "").strip(" |—-")
        results["pinterest"] = post_pinterest_pin(
            video_path, title, meta.get("description", ""), youtube_video_id)
    except Exception:
        traceback.print_exc()
        print("  crosspost: Pinterest failed (non-fatal)")
    return results

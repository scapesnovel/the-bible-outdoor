#!/usr/bin/env python3
"""Upload videos to YouTube via the YouTube Data API v3 (free quota: 10,000 units/day).

Auth: OAuth refresh token stored in env vars (GitHub Actions secrets):
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN

Uploads cost 1600 units each -> 2 uploads/day = 3200 units. Well within quota.
"""
import os, sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import google.oauth2.credentials
import googleapiclient.discovery
import googleapiclient.http

def _creds():
    missing = [k for k in ("YT_REFRESH_TOKEN", "YT_CLIENT_ID", "YT_CLIENT_SECRET")
               if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"FATAL: missing GitHub secrets: {', '.join(missing)}")
    return google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube"],
    )

def yt_client():
    return googleapiclient.discovery.build("youtube", "v3", credentials=_creds())

def check_token():
    """Preflight: verify the refresh token works BEFORE spending ~30 min
    rendering video. Dies with a loud, actionable message if it's dead
    (classic cause: OAuth app left in 'Testing' mode -> Google revokes
    refresh tokens after 7 days)."""
    import google.auth.transport.requests
    import google.auth.exceptions
    creds = _creds()
    try:
        creds.refresh(google.auth.transport.requests.Request())
        print("Token preflight: YouTube credentials OK.")
    except google.auth.exceptions.RefreshError as e:
        print("=" * 64)
        print("FATAL: YouTube refresh token is EXPIRED or REVOKED.")
        print(f"  ({e})")
        print()
        print("FIX (5 minutes, one time):")
        print("  1. console.cloud.google.com -> APIs & Services ->")
        print("     OAuth consent screen -> click PUBLISH APP")
        print("     (Testing mode kills refresh tokens after 7 days!)")
        print("  2. On your PC: python3 pipeline/get_refresh_token.py \\")
        print("       <CLIENT_ID> <CLIENT_SECRET>")
        print("  3. GitHub repo -> Settings -> Secrets and variables ->")
        print("     Actions -> update YT_REFRESH_TOKEN")
        print("=" * 64)
        raise SystemExit(1)

def upload(meta_path, thumbnail=None, privacy="public", publish_at_iso=None):
    """Upload a video. If publish_at_iso is given, it is uploaded as private
    and scheduled to go public at that exact UTC time (prime-time targeting)."""
    meta = json.loads(pathlib.Path(meta_path).read_text())
    yt = yt_client()
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    if publish_at_iso:
        status = {"privacyStatus": "private", "publishAt": publish_at_iso,
                  "selfDeclaredMadeForKids": False}
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": meta.get("categoryId", "22"),
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": status,
    }
    media = googleapiclient.http.MediaFileUpload(meta["file"], chunksize=8 * 1024 * 1024,
                                                 resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"  upload {int(status.progress() * 100)}%")
    vid = resp["id"]
    when = f" (goes live {publish_at_iso})" if publish_at_iso else ""
    print(f"UPLOADED: https://youtu.be/{vid}  ({meta['type']}, day {meta['day']}){when}")

    if thumbnail and pathlib.Path(thumbnail).exists() and meta["type"] == "longform":
        try:
            yt.thumbnails().set(videoId=vid,
                                media_body=googleapiclient.http.MediaFileUpload(str(thumbnail))).execute()
            print("  custom thumbnail set")
        except Exception as e:
            print(f"  thumbnail skipped (channel may need verification): {e}")

    # Growth: add to the right playlist (binge-watching -> watch time -> monetization)
    try:
        add_to_playlist(yt, vid, "Daily Scripture Meditations" if meta["type"] == "longform"
                        else "Daily Verse Shorts")
    except Exception as e:
        print(f"  playlist skipped: {e}")
    return vid

_playlist_cache = {}

def add_to_playlist(yt, video_id, playlist_title):
    """Find-or-create a playlist and append the video."""
    if playlist_title not in _playlist_cache:
        r = yt.playlists().list(part="snippet", mine=True, maxResults=50).execute()
        for p in r.get("items", []):
            if p["snippet"]["title"] == playlist_title:
                _playlist_cache[playlist_title] = p["id"]
                break
        else:
            p = yt.playlists().insert(part="snippet,status", body={
                "snippet": {"title": playlist_title,
                            "description": "New videos every day — The Bible Outdoor."},
                "status": {"privacyStatus": "public"}}).execute()
            _playlist_cache[playlist_title] = p["id"]
    yt.playlistItems().insert(part="snippet", body={
        "snippet": {"playlistId": _playlist_cache[playlist_title],
                    "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()
    print(f"  added to playlist: {playlist_title}")

if __name__ == "__main__":
    meta_path = sys.argv[1]
    thumb = sys.argv[2] if len(sys.argv) > 2 else None
    upload(meta_path, thumb)

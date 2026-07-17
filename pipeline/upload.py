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

def yt_client():
    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube"],
    )
    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)

def upload(meta_path, thumbnail=None, privacy="public"):
    meta = json.loads(pathlib.Path(meta_path).read_text())
    yt = yt_client()
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": meta.get("categoryId", "22"),
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
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
    print(f"UPLOADED: https://youtu.be/{vid}  ({meta['type']}, day {meta['day']})")

    if thumbnail and pathlib.Path(thumbnail).exists() and meta["type"] == "longform":
        try:
            yt.thumbnails().set(videoId=vid,
                                media_body=googleapiclient.http.MediaFileUpload(str(thumbnail))).execute()
            print("  custom thumbnail set")
        except Exception as e:
            print(f"  thumbnail skipped (channel may need verification): {e}")
    return vid

if __name__ == "__main__":
    meta_path = sys.argv[1]
    thumb = sys.argv[2] if len(sys.argv) > 2 else None
    upload(meta_path, thumb)

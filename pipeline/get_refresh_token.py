#!/usr/bin/env python3
"""ONE-TIME human-assisted step: obtain a YouTube OAuth refresh token.

Run on any machine with a browser:
  pip install google-auth-oauthlib
  python3 get_refresh_token.py CLIENT_ID CLIENT_SECRET

It opens a browser, you sign in with the channel's Google account and approve.
It then prints the YT_REFRESH_TOKEN to paste into GitHub Secrets.
"""
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

def main():
    client_id, client_secret = sys.argv[1], sys.argv[2]
    config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(config, SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    print("\n" + "=" * 60)
    print("SUCCESS! Add these three GitHub Secrets:")
    print("=" * 60)
    print(f"YT_CLIENT_ID     = {client_id}")
    print(f"YT_CLIENT_SECRET = {client_secret}")
    print(f"YT_REFRESH_TOKEN = {creds.refresh_token}")
    print("=" * 60)

if __name__ == "__main__":
    main()

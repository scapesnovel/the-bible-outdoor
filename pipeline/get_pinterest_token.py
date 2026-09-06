#!/usr/bin/env python3
"""One-time helper: exchange a Pinterest OAuth code for a refresh token.

Browser-only flow (like the YouTube OAuth Playground trick):
 1. Visit (replace YOUR_APP_ID):
    https://www.pinterest.com/oauth/?client_id=YOUR_APP_ID&redirect_uri=https://localhost/&response_type=code&scope=boards:read,pins:read,pins:write
 2. Approve. The browser lands on https://localhost/?code=XXXX (page won't load — fine).
    Copy the code from the address bar.
 3. Run: python3 pipeline/get_pinterest_token.py APP_ID APP_SECRET CODE
 4. Save the printed refresh_token as the PIN_REFRESH_TOKEN GitHub secret.
"""
import sys, base64, json, urllib.request, urllib.parse

def main():
    if len(sys.argv) != 4:
        print(__doc__); sys.exit(1)
    app_id, secret, code = sys.argv[1:4]
    basic = base64.b64encode(f"{app_id}:{secret}".encode()).decode()
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": "https://localhost/",
    }).encode()
    req = urllib.request.Request(
        "https://api.pinterest.com/v5/oauth/token", data=data,
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"})
    j = json.loads(urllib.request.urlopen(req).read())
    print(json.dumps(j, indent=2))
    print("\n=> GitHub secret PIN_REFRESH_TOKEN =", j.get("refresh_token"))

if __name__ == "__main__":
    main()

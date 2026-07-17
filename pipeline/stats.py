#!/usr/bin/env python3
"""Channel performance monitor. Runs daily via GitHub Actions, appends to data/stats_log.json
and writes a human-readable report to STATS.md — so performance tracking is automatic."""
import os, sys, json, pathlib, datetime
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from upload import yt_client

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "stats_log.json"
MD = ROOT / "STATS.md"

def main():
    yt = yt_client()
    ch = yt.channels().list(part="statistics,snippet,contentDetails", mine=True).execute()["items"][0]
    st = ch["statistics"]
    uploads_pl = ch["contentDetails"]["relatedPlaylists"]["uploads"]

    vids, page = [], None
    while len(vids) < 100:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads_pl,
                                    maxResults=50, pageToken=page).execute()
        vids += [i["contentDetails"]["videoId"] for i in r["items"]]
        page = r.get("nextPageToken")
        if not page:
            break

    video_rows = []
    for i in range(0, len(vids), 50):
        r = yt.videos().list(part="statistics,snippet", id=",".join(vids[i:i+50])).execute()
        for v in r["items"]:
            video_rows.append({
                "id": v["id"], "title": v["snippet"]["title"][:70],
                "published": v["snippet"]["publishedAt"][:10],
                "views": int(v["statistics"].get("viewCount", 0)),
                "likes": int(v["statistics"].get("likeCount", 0)),
                "comments": int(v["statistics"].get("commentCount", 0)),
            })
    video_rows.sort(key=lambda x: -x["views"])

    snap = {
        "date": datetime.date.today().isoformat(),
        "subscribers": int(st.get("subscriberCount", 0)),
        "total_views": int(st.get("viewCount", 0)),
        "video_count": int(st.get("videoCount", 0)),
        "videos": video_rows,
    }
    log = json.loads(LOG.read_text()) if LOG.exists() else []
    log = [s for s in log if s["date"] != snap["date"]] + [snap]
    LOG.write_text(json.dumps(log, indent=1))

    lines = [f"# 📊 {ch['snippet']['title']} — Performance Report",
             f"_Updated: {snap['date']}_\n",
             f"| Metric | Value |", "|---|---|",
             f"| Subscribers | **{snap['subscribers']}** |",
             f"| Total views | **{snap['total_views']}** |",
             f"| Videos published | **{snap['video_count']}** |"]
    if len(log) > 1:
        prev = log[-2]
        lines.append(f"| Subs gained (24h) | +{snap['subscribers'] - prev['subscribers']} |")
        lines.append(f"| Views gained (24h) | +{snap['total_views'] - prev['total_views']} |")
    lines += ["\n## Top videos", "| Views | Likes | Title | Published |", "|---|---|---|---|"]
    for v in video_rows[:15]:
        lines.append(f"| {v['views']} | {v['likes']} | {v['title']} | {v['published']} |")
    MD.write_text("\n".join(lines) + "\n")
    print(MD.read_text())

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""ONE-TIME: download the complete BSB Bible (66 books, 1189 chapters, ~31k verses)
into data/bible.json.gz so the pipeline is fully offline and can pick ANY verse."""
import json, gzip, time, urllib.request, pathlib, sys
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bible.json.gz"
BASE = "https://bible.helloao.org/api/BSB"

def get(url, retries=5):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BibleOutdoor/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(4 * (i + 1))

def verse_text(content_items):
    parts = []
    for x in content_items:
        if isinstance(x, str):
            parts.append(x)
        elif isinstance(x, dict) and "text" in x:
            parts.append(x["text"])
    return " ".join(" ".join(parts).split())

def fetch_chapter(args):
    code, name, ch = args
    d = get(f"{BASE}/{code}/{ch}.json")
    verses = {}
    for c in d["chapter"]["content"]:
        if c.get("type") == "verse":
            t = verse_text(c["content"])
            if t:
                verses[str(c["number"])] = t
    return code, name, ch, verses

def main():
    books = get(f"{BASE}/books.json")["books"]
    jobs = []
    for b in books:
        for ch in range(1, b["numberOfChapters"] + 1):
            jobs.append((b["id"], b["name"], ch))
    print(f"{len(books)} books, {len(jobs)} chapters to fetch")

    bible = {}  # book_name -> {chapter -> {verse -> text}}
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for code, name, ch, verses in ex.map(fetch_chapter, jobs):
            bible.setdefault(name, {})[str(ch)] = verses
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(jobs)} chapters")

    total = sum(len(v) for chs in bible.values() for v in chs.values())
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump(bible, f, ensure_ascii=False)
    print(f"Saved {total} verses across {len(bible)} books -> {OUT} ({OUT.stat().st_size//1024} KB)")

if __name__ == "__main__":
    main()

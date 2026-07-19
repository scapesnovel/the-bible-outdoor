#!/usr/bin/env python3
"""Pre-fetch all Bible passages into data/verses.json.

Translation: Berean Standard Bible (BSB) — modern English, reads like the NIV,
but completely free for any use (public-domain dedication). Source: bible.helloao.org.
"""
import json, time, urllib.request, pathlib, sys, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION = "BSB"

BOOKS = {
    "Genesis": "GEN", "Exodus": "EXO", "Leviticus": "LEV", "Numbers": "NUM",
    "Deuteronomy": "DEU", "Joshua": "JOS", "Judges": "JDG", "Ruth": "RUT",
    "1 Samuel": "1SA", "2 Samuel": "2SA", "1 Kings": "1KI", "2 Kings": "2KI",
    "1 Chronicles": "1CH", "2 Chronicles": "2CH", "Ezra": "EZR", "Nehemiah": "NEH",
    "Esther": "EST", "Job": "JOB", "Psalms": "PSA", "Proverbs": "PRO",
    "Ecclesiastes": "ECC", "Song of Solomon": "SNG", "Isaiah": "ISA",
    "Jeremiah": "JER", "Lamentations": "LAM", "Ezekiel": "EZK", "Daniel": "DAN",
    "Hosea": "HOS", "Joel": "JOL", "Amos": "AMO", "Obadiah": "OBA", "Jonah": "JON",
    "Micah": "MIC", "Nahum": "NAM", "Habakkuk": "HAB", "Zephaniah": "ZEP",
    "Haggai": "HAG", "Zechariah": "ZEC", "Malachi": "MAL",
    "Matthew": "MAT", "Mark": "MRK", "Luke": "LUK", "John": "JHN", "Acts": "ACT",
    "Romans": "ROM", "1 Corinthians": "1CO", "2 Corinthians": "2CO",
    "Galatians": "GAL", "Ephesians": "EPH", "Philippians": "PHP",
    "Colossians": "COL", "1 Thessalonians": "1TH", "2 Thessalonians": "2TH",
    "1 Timothy": "1TI", "2 Timothy": "2TI", "Titus": "TIT", "Philemon": "PHM",
    "Hebrews": "HEB", "James": "JAS", "1 Peter": "1PE", "2 Peter": "2PE",
    "1 John": "1JN", "2 John": "2JN", "3 John": "3JN", "Jude": "JUD",
    "Revelation": "REV",
}

_chapter_cache = {}

def parse_ref(ref):
    m = re.match(r"^(.*?)\s+(\d+):(\d+)(?:-(\d+))?$", ref.strip())
    if not m:
        raise ValueError(f"Bad ref: {ref}")
    book, ch, v1, v2 = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
    return BOOKS[book], ch, v1, int(v2) if v2 else v1

def get_chapter(code, ch):
    key = (code, ch)
    if key in _chapter_cache:
        return _chapter_cache[key]
    url = f"https://bible.helloao.org/api/{TRANSLATION}/{code}/{ch}.json"
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BibleOutdoor/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode())
            _chapter_cache[key] = d
            return d
        except Exception as e:
            print(f"  retry {attempt+1} for {code} {ch}: {e}", file=sys.stderr)
            time.sleep(6 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {code} {ch}")

def verse_text(content_items):
    parts = []
    for x in content_items:
        if isinstance(x, str):
            parts.append(x)
        elif isinstance(x, dict):
            if "text" in x:
                parts.append(x["text"])
            elif "heading" in x or "noteId" in x or x.get("lineBreak"):
                continue
    return " ".join(" ".join(parts).split())

def fetch(ref):
    code, ch, v1, v2 = parse_ref(ref)
    d = get_chapter(code, ch)
    texts = []
    for c in d["chapter"]["content"]:
        if c.get("type") == "verse" and v1 <= c["number"] <= v2:
            texts.append(verse_text(c["content"]))
    if len(texts) != (v2 - v1 + 1):
        raise RuntimeError(f"{ref}: expected {v2-v1+1} verses, got {len(texts)}")
    return {"reference": ref, "text": " ".join(texts)}

if __name__ == "__main__":
    plan = json.loads((ROOT / "data/plan.json").read_text())
    refs = set()
    for day in plan["days"]:
        for p in day["passages"]:
            refs.add(p["ref"])
        refs.add(day["short"]["ref"])

    out_path = ROOT / "data/verses.json"
    cache = {}
    for i, ref in enumerate(sorted(refs)):
        cache[ref] = fetch(ref)
        out_path.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
        print(f"[{i+1}/{len(refs)}] {ref} -> {cache[ref]['text'][:60]}...")
        time.sleep(0.4)
    print(f"Saved {len(cache)} passages ({TRANSLATION}) to {out_path}")

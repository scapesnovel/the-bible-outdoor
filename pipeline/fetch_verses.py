#!/usr/bin/env python3
"""Pre-fetch all Bible passages (WEB translation, public domain) into data/verses.json."""
import json, time, urllib.request, urllib.parse, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
plan = json.loads((ROOT / "data/plan.json").read_text())

refs = set()
for d in plan["days"]:
    for p in d["passages"]:
        refs.add(p["ref"])
    refs.add(d["short"]["ref"])

out_path = ROOT / "data/verses.json"
cache = json.loads(out_path.read_text()) if out_path.exists() else {}

def fetch(ref):
    url = "https://bible-api.com/" + urllib.parse.quote(ref) + "?translation=web"
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TheBibleOutdoor/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode())
            text = " ".join(v["text"].replace("\n", " ").strip() for v in d["verses"])
            text = " ".join(text.split())
            # WEB uses "Yahweh"; most listeners expect "the LORD" — normalize for narration
            spoken = text.replace("Yahweh's", "the LORD's").replace("Yahweh", "the LORD")
            return {"reference": d["reference"], "text": spoken}
        except Exception as e:
            print(f"  retry {attempt+1} for {ref}: {e}", file=sys.stderr)
            time.sleep(8 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {ref}")

todo = [r for r in sorted(refs) if r not in cache]
print(f"{len(refs)} unique refs, {len(todo)} to fetch")
for i, ref in enumerate(todo):
    cache[ref] = fetch(ref)
    out_path.write_text(json.dumps(cache, indent=1, ensure_ascii=False))  # save incrementally
    print(f"[{i+1}/{len(todo)}] {ref} -> {cache[ref]['text'][:60]}...")
    time.sleep(2.0)

out_path.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
print(f"Saved {len(cache)} passages to {out_path}")

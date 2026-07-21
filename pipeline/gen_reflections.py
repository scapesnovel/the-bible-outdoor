#!/usr/bin/env python3
"""One-time (sandbox-only) generator: a unique, verse-specific encouragement
for EVERY passage the judgment picker could ever choose.

Output: data/reflections.json.gz  {display_ref: {"text": passage, "refl": encouragement}}
Runtime (GitHub Actions) only READS this bank — zero API calls, zero failure modes.

Resumable: saves incrementally every batch; re-running skips done refs.
"""
import sys, os, json, gzip, pathlib, time, re
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import verse_picker as vp

DATA = vp.DATA
BANK_PATH = DATA / "reflections.json.gz"
BATCH = 25
WORKERS = 5
MODEL = "gpt-5-mini"

SYSTEM = (
    "You write brief spoken encouragements for a Christian daily-verse YouTube channel. "
    "For each Bible passage given, write 2 sentences (30-45 words total) that: "
    "1) engage the SPECIFIC content and imagery of that verse (never generic), "
    "2) speak directly to the viewer ('you'), warm pastoral tone, "
    "3) end with one concrete encouragement or gentle call to action for today. "
    "No emojis, no hashtags, no verse re-quoting, no 'this verse says'. "
    "Return STRICT JSON: {\"items\": [{\"ref\": \"...\", \"refl\": \"...\"}]} with every ref echoed exactly."
)

def build_pool():
    """All complete-thought passages in the picker's judgment range."""
    bible = vp.load_bible()
    pool = {}
    for theme, (strong, weak) in vp.THEME_TERMS.items():
        cands = []
        for book, chs in bible.items():
            for ch, vs in chs.items():
                for vn, t in vs.items():
                    sc = vp._score(t, book, strong, weak)
                    if sc > 0:
                        cands.append((sc, f"{book} {ch}:{vn}", t))
        cands.sort(key=lambda x: -x[0])
        for sc, ref, t in cands[:150]:
            exp = vp._expand_to_thought(bible, ref, set())
            if exp is None:
                continue
            refs, text, disp = exp
            pool.setdefault(disp, text)
    return pool

def load_bank():
    if BANK_PATH.exists():
        with gzip.open(BANK_PATH, "rt", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_bank(bank):
    tmp = BANK_PATH.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False)
    tmp.replace(BANK_PATH)

def _client():
    from openai import OpenAI
    return OpenAI()  # OPENAI_API_KEY / OPENAI_BASE_URL from env

def gen_batch(client, items):
    """items: list of (ref, text). Returns {ref: refl}."""
    user = "\n\n".join(f"[{r}] {t}" for r, t in items)
    for attempt in range(4):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": user}],
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)
            out = {}
            for it in data.get("items", []):
                ref, refl = it.get("ref", "").strip(), " ".join(it.get("refl", "").split())
                if ref and 15 <= len(refl.split()) <= 70:
                    out[ref] = refl
            if out:
                return out
        except Exception as e:
            print(f"    batch retry {attempt+1}: {type(e).__name__}: {e}", flush=True)
            time.sleep(3 * (attempt + 1))
    return {}

def main():
    pool = build_pool()
    bank = load_bank()
    todo = [(r, t) for r, t in sorted(pool.items()) if r not in bank]
    print(f"Pool: {len(pool)} passages | done: {len(bank)} | to generate: {len(todo)}", flush=True)
    if not todo:
        print("Bank complete."); return

    client = _client()
    batches = [todo[i:i+BATCH] for i in range(0, len(todo), BATCH)]
    done_since_save = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(gen_batch, client, b): b for b in batches}
        for n, fut in enumerate(as_completed(futs), 1):
            batch = futs[fut]
            got = fut.result()
            # store with the passage text so runtime never needs the Bible for lookup
            for r, t in batch:
                if r in got:
                    bank[r] = {"refl": got[r]}
            done_since_save += len(got)
            print(f"  [{n}/{len(batches)}] +{len(got)}/{len(batch)}  total={len(bank)}", flush=True)
            if done_since_save >= 100:
                save_bank(bank); done_since_save = 0
    save_bank(bank)
    missing = len(pool) - len(bank)
    print(f"DONE: {len(bank)} reflections saved -> {BANK_PATH} | missing: {missing} (template fallback covers these)")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build the daily vertical Short (~45-60s): hook -> verse -> reflection -> CTA."""
import sys, json, pathlib, shutil, random
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import ROOT, ASSETS, OUT, CHANNEL_NAME, get_day_entry, load_verses, display_ref
from tts import tts, VOICE_SHORT
from text_render import make_card
import av

W, H = 1080, 1920

def build(day_number=None, cycle=1):
    plan, entry, day_number = get_day_entry(day_number, cycle)
    cycle = entry.get("_cycle", cycle)
    verses = load_verses()
    work = OUT / f"day{day_number:02d}_short_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    final_dir = OUT / f"day{day_number:02d}"
    final_dir.mkdir(parents=True, exist_ok=True)

    s = entry["short"]
    v = verses[s["ref"]]
    ref_disp = display_ref(v["reference"])
    rng = random.Random(day_number * 7 + cycle * 131)
    bgs = sorted((ASSETS / "backgrounds_vertical").glob("*.jpg"))
    bg = bgs[(day_number + cycle) % len(bgs)]
    music = rng.choice(sorted((ASSETS / "music").glob("*.mp3")))

    parts = [
        ("hook", s["hook"],
         dict(title=s["hook"], ref=CHANNEL_NAME, title_size=72, ref_size=42), 0.4),
        ("verse", f"{ref_disp} says: ... {v['text']}",
         dict(body=f"\u201C{v['text']}\u201D", ref=f"— {ref_disp}", body_start=72), 0.6),
        ("refl", s["reflection"],
         dict(body=s["reflection"], body_start=68), 0.5),
        ("cta", "Follow for one verse every single day. God bless you.",
         dict(title="One verse. Every day.", ref="Subscribe — " + CHANNEL_NAME, title_size=72, ref_size=44), 0.3),
    ]

    seg_files = []
    for idx, (name, speech, card_kwargs, gap) in enumerate(parts):
        a = work / f"{name}.mp3"
        tts(speech, a, voice=VOICE_SHORT, rate="-4%")
        a_pad = work / f"{name}_pad.m4a"
        av.combine_audio([(a, gap)], a_pad, tail_silence=0)
        card = work / f"{name}.png"
        make_card(W, H, out_path=card, margin_ratio=0.08, **card_kwargs)
        seg = work / f"{name}.mp4"
        av.kenburns_segment(bg, card, a_pad, seg, W, H, fps=30, zoom_total=0.14,
                            direction=1 if idx % 2 == 0 else -1)
        seg_files.append(seg)
        print(f"  short segment {name}: OK")

    raw = work / "concat_raw.mp4"
    av.concat_segments(seg_files, raw, work)
    final = final_dir / f"day{day_number:02d}_short.mp4"
    av.mix_music(raw, music, final, music_vol=0.12)
    dur = av.duration(final)
    print(f"SHORT day {day_number}: {final} ({dur:.0f}s)")

    kw = entry["keywords"]
    title = f"{s['hook']} | {ref_disp} #shorts"
    if len(title) > 100:
        title = f"{ref_disp} — {entry['theme']} #shorts"
    description = (
        f"{s['reflection']}\n\n\u201C{v['text']}\u201D — {ref_disp} (BSB)\n\n"
        "🙏 One verse every day. Subscribe and grow your faith daily.\n\n"
        f"#shorts #bible #bibleverse #{kw[0].replace(' ','')} #faith #jesus #dailyverse"
    )
    tags = list(dict.fromkeys(kw + ["shorts", "bible verse", "daily verse", "faith", "jesus", "scripture"]))[:25]
    meta = {"title": title[:100], "description": description[:4900], "tags": tags,
            "categoryId": "22", "day": day_number, "cycle": cycle,
            "theme": entry["theme"], "type": "short", "file": str(final)}
    (final_dir / "short_meta.json").write_text(json.dumps(meta, indent=1))
    shutil.rmtree(work)
    return final, meta

if __name__ == "__main__":
    day = int(sys.argv[1]) if len(sys.argv) > 1 else None
    build(day)

#!/usr/bin/env python3
"""Build a CUSTOM vertical Short from an owner-submitted queue item.

Identical production pipeline to build_short.py (voice-over, background image,
Ken Burns zoom, background music, caption cards) — only the verse and the
explanation come from the channel owner instead of the bot.

Custom verses are NEVER burned to the no-repeat ledger: the owner's
explanation is personal, so the bot may still feature the same verse later
with its own reflection.
"""
import sys, json, pathlib, shutil, random
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import ROOT, ASSETS, OUT, CHANNEL_NAME, display_ref
import verse_picker as vp
from tts import tts, VOICE_SHORT
import metadata
from text_render import make_card
import av

W, H = 1080, 1920

_CUSTOM_HOOKS = [
    "A verse I chose for you today.",
    "This verse would not leave my heart today.",
    "Today's verse comes straight from the heart.",
    "I picked this verse just for you today.",
    "Stop scrolling — this one is for you.",
    "God put this verse on my heart today.",
]

def _seed_from_id(item_id):
    return sum(ord(c) * (i + 7) for i, c in enumerate(item_id))

def build(item):
    """item = queue entry dict with keys:
       id, display_ref, text, explanation, publish_at  (hook optional)"""
    iid = item["id"]
    seed = _seed_from_id(iid)
    rng = random.Random(seed)
    ref_disp = display_ref(item["display_ref"])
    text = item["text"].strip()
    explanation = item["explanation"].strip()
    hook = (item.get("hook") or "").strip() or rng.choice(_CUSTOM_HOOKS)

    work = OUT / f"custom_{iid}_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    final_dir = OUT / "custom"
    final_dir.mkdir(parents=True, exist_ok=True)

    bgs = sorted((ASSETS / "backgrounds_vertical").glob("*.jpg"))
    bg = bgs[seed % len(bgs)]
    music = rng.choice(sorted((ASSETS / "music").glob("*.mp3")))

    parts = [
        ("hook", hook,
         dict(title=hook, ref=CHANNEL_NAME, title_size=72, ref_size=42), 0.4),
        ("verse", f"{ref_disp} says: ... {text}",
         dict(body=f"\u201C{text}\u201D", ref=f"— {ref_disp}", body_start=72), 0.6),
        ("refl", explanation,
         dict(body=explanation, body_start=68), 0.5),
        ("cta", vp.cta_line(seed=seed * 3 + 1),
         dict(title="One verse. Every day.", ref="Subscribe — " + CHANNEL_NAME,
              title_size=72, ref_size=44), 0.3),
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
        print(f"  custom segment {name}: OK")

    raw = work / "concat_raw.mp4"
    av.concat_segments(seg_files, raw, work)
    final = final_dir / f"custom_{iid}.mp4"
    av.mix_music(raw, music, final, music_vol=0.12)
    dur = av.duration(final)
    print(f"CUSTOM SHORT {iid}: {final} ({dur:.0f}s)")

    # Variety engine: unique title shape / description / hashtags per video
    title = metadata.short_title(hook, ref_disp, seed=seed)
    description = metadata.short_description(
        explanation, text, ref_disp, seed=seed, theme_key="custom")
    tags = metadata.short_tags(theme_key="custom", seed=seed)
    meta = {"title": title[:100], "description": description[:4900], "tags": tags,
            "categoryId": "22", "day": 0, "cycle": 0, "theme": "custom",
            "type": "short", "file": str(final),
            "verse_refs": []}  # empty on purpose: custom verses never burn the ledger
    meta_path = final_dir / f"custom_{iid}_meta.json"
    meta_path.write_text(json.dumps(meta, indent=1))
    shutil.rmtree(work)
    return final, meta_path

if __name__ == "__main__":
    # Test: build from a JSON string or a queue item id
    item = json.loads(sys.argv[1])
    build(item)

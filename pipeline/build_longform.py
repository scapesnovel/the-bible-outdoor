#!/usr/bin/env python3
"""Build the daily long-form Scripture meditation video (1080p, ~10-12 min).

Structure per passage: intro -> [verse read slowly -> reflection -> pause] x5 -> prayer -> outro.
"""
import sys, json, pathlib, shutil, random
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import ROOT, ASSETS, OUT, CHANNEL_NAME, get_day_entry, display_ref
import verse_picker as vp
from tts import tts, VOICE_MAIN
from text_render import make_card
import av

W, H = 1920, 1080

def build(day_number=None, cycle=1):
    plan, entry, day_number = get_day_entry(day_number, cycle)
    cycle = entry.get("_cycle", cycle)
    # Fresh verses picked by judgment from the FULL Bible — never repeated.
    sel = vp.pick_for_episode(day_number, cycle, plan_days=len(plan["days"]))
    theme_key, ep_no = sel["theme_key"], sel["episode"]
    passages = [{"ref": p["ref"], "text": p["text"],
                 "reflection": vp.reflect(p, theme_key, seed=ep_no * 31 + i)}
                for i, p in enumerate(sel["longform"], 1)]
    work = OUT / f"day{day_number:02d}_long_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    final_dir = OUT / f"day{day_number:02d}"
    final_dir.mkdir(parents=True, exist_ok=True)

    bgs = sorted((ASSETS / "backgrounds").glob("*.jpg"))
    rng = random.Random(day_number)  # deterministic per day
    rng.shuffle(bgs)
    music = rng.choice(sorted((ASSETS / "music").glob("*.mp3")))

    theme = entry["theme"]
    segments = []  # (name, spoken_text, card_kwargs, gap_after)

    intro_text = (f"Welcome to {CHANNEL_NAME}. Today's meditation: {theme}. "
                  f"{entry['intro']} Take a slow, deep breath... let your heart grow quiet... "
                  f"and let God's word speak to you.")
    segments.append(("intro", intro_text,
                     dict(title=CHANNEL_NAME, body=f"Today's Meditation\n{theme}".replace("\n", " — "),
                          ref="Take a deep breath, and be still."), 1.2))

    for i, p in enumerate(passages, 1):
        ref_disp = display_ref(p["ref"])
        verse_speech = f"{ref_disp}. ... {p['text']}"
        segments.append((f"verse{i}", verse_speech,
                         dict(body=f"\u201C{p['text']}\u201D", ref=f"— {ref_disp} (BSB)"), 2.5))
        # lectio divina: hear the same words a second time, slower
        segments.append((f"verse{i}b", f"Listen once more, and let these words settle into your heart. ... {p['text']}",
                         dict(body=f"\u201C{p['text']}\u201D", ref=f"— {ref_disp} (BSB)"), 3.0))
        segments.append((f"refl{i}", p["reflection"] + " ... Sit with that for a moment.",
                         dict(title=theme, body=p["reflection"]), 3.5))

    prayer_speech = "Let us pray together. ... " + entry["prayer"]
    segments.append(("prayer", prayer_speech,
                     dict(title="Let Us Pray", body=entry["prayer"]), 1.2))

    outro_text = ("May the Lord bless you and keep you today. If this meditation strengthened you, "
                  "subscribe and share it with someone who needs it. New Scripture meditations every day. "
                  f"See you tomorrow on {CHANNEL_NAME}.")
    segments.append(("outro", outro_text,
                     dict(title=CHANNEL_NAME, body="New meditations every day.\nSubscribe & grow with us.".replace("\n", " "),
                          ref="Numbers 6:24 — The LORD bless you, and keep you."), 0.5))

    # 1) TTS + cards + Ken Burns segments
    seg_files = []
    for idx, (name, speech, card_kwargs, gap) in enumerate(segments):
        a = work / f"{name}.mp3"
        tts(speech, a, voice=VOICE_MAIN, rate="-12%", pitch="-2Hz")
        card = work / f"{name}.png"
        make_card(W, H, out_path=card, **card_kwargs)
        # pad narration with the gap (silence) so pacing feels meditative
        a_pad = work / f"{name}_pad.m4a"
        av.combine_audio([(a, gap)], a_pad, tail_silence=0)
        bg = bgs[(idx // 3) % len(bgs)]  # same scene across a verse group, new scene per passage
        seg = work / f"{name}.mp4"
        av.kenburns_segment(bg, card, a_pad, seg, W, H, zoom_total=0.08,
                            direction=1 if idx % 2 == 0 else -1)
        seg_files.append(seg)
        print(f"  segment {name}: OK")

    # 2) concat + music
    raw = work / "concat_raw.mp4"
    av.concat_segments(seg_files, raw, work)
    final = final_dir / f"day{day_number:02d}_longform.mp4"
    av.mix_music(raw, music, final)
    dur = av.duration(final)
    print(f"LONGFORM day {day_number}: {final} ({dur/60:.1f} min)")

    # 3) metadata
    refs = [display_ref(p["ref"]) for p in passages]
    kw = entry["keywords"]
    ep = ep_no  # global episode number, never repeats
    angles = ["5 Bible Verses & Guided Prayer", "Bible Verses to Meditate On",
              "Scripture & Prayer for Your Soul", "Guided Bible Meditation"]
    title = f"{theme} — {angles[(cycle - 1) % len(angles)]} | Daily Scripture Meditation (Day {ep})"
    description = (
        f"{entry['intro']}\n\n"
        f"Today's meditation on {theme} walks slowly through five Scriptures, with reflections and a closing prayer.\n\n"
        "In this video:\n" +
        "\n".join(f"  • {r}" for r in refs) +
        "\n\n🙏 SUBSCRIBE for a new Scripture meditation every day — where God's Word meets God's creation.\n\n"
        "Share this with someone who needs it today.\n\n"
        "Scripture quotations are from the Berean Standard Bible (BSB), used with permission.\n\n"
        f"#Bible #Scripture #{kw[0].title().replace(' ','')} #DailyDevotional #ChristianMeditation #Prayer #Faith"
    )
    tags = list(dict.fromkeys(
        kw + ["bible verses", "daily devotional", "scripture meditation", "guided prayer",
              "christian meditation", "bible study", "morning prayer", "faith", theme.lower()]
    ))[:30]
    meta = {"title": title[:100], "description": description[:4900], "tags": tags,
            "categoryId": "22", "day": day_number, "cycle": cycle, "episode": ep,
            "theme": theme, "type": "longform", "file": str(final),
            "verse_refs": [p["ref"] for p in passages] + [sel["short"]["ref"]]}
    (final_dir / "longform_meta.json").write_text(json.dumps(meta, indent=1))
    shutil.rmtree(work)
    return final, meta

if __name__ == "__main__":
    day = int(sys.argv[1]) if len(sys.argv) > 1 else None
    build(day)

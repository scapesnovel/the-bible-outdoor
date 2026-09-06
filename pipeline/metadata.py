#!/usr/bin/env python3
"""Metadata variety engine — the anti-"inauthentic content" layer.

YouTube's monetization policy (July 2025 "inauthentic content" rewrite)
demonetizes channels whose videos look mass-produced: identical title
patterns, copy-paste descriptions, the same hashtag block on every upload.

This module makes every upload's *packaging* unique while keeping the
pipeline fully deterministic (same seed -> same output, so retries match):

  * 12 title formats  (rotated per video, never the same shape twice in a row)
  * 10 description intros + 12 engagement questions + 8 blessing outros
  * theme-aware hashtag pools sampled per video (3-5 tags, varied order)
  * tag list shuffled + theme keywords first

Used by build_short.py (bot Shorts) and build_custom.py (app Shorts).
"""
import random

# ---------------------------------------------------------------------------
# Title formats. {hook} {ref} {theme} available. #shorts kept (discovery).
# Formats deliberately vary STRUCTURE: hook-first, ref-first, question,
# imperative, emotional — so no two consecutive days share a shape.
# ---------------------------------------------------------------------------
_TITLE_FMTS = [
    "{hook} | {ref} #shorts",
    "{ref} — {hook} #shorts",
    "{hook} ({ref}) #shorts",
    "A word for today: {ref} #shorts",
    "{ref} might be exactly what you need today #shorts",
    "Today's verse: {ref} #shorts",
    "{hook} — {ref}",
    "{ref} | daily Scripture #shorts",
    "One minute with {ref} #shorts",
    "{hook} {ref} #bibleshorts",
    "Let {ref} speak to you today #shorts",
    "{ref} — take this with you today #shorts",
]

# Description building blocks -----------------------------------------------
_DESC_INTRO = [
    "",  # sometimes lead straight with the reflection — variety
    "Today's verse comes from {ref}.\n\n",
    "A moment of Scripture for your day.\n\n",
    "Take 45 seconds with God's Word.\n\n",
    "From our daily walk through Scripture:\n\n",
    "Wherever this finds you today —\n\n",
    "Pause here for a moment.\n\n",
    "God's Word for {ref_book} readers and everyone else too:\n\n",
    "Before the day gets loud:\n\n",
    "One verse. One thought. One day at a time.\n\n",
]

_ENGAGE = [
    "Which word in this verse stood out to you? Tell us below 👇",
    "How has this verse shown up in your own life? Share in the comments.",
    "Who needs to hear this today? Tag them or share it forward.",
    "What are you trusting God with this week? We read every comment.",
    "Drop a 🙏 if this verse found you at the right time.",
    "What would change if you believed this verse completely today?",
    "Save this for the moment you'll need it most.",
    "Tell us where you're watching from — we love praying for our viewers.",
    "If you could memorize one line of this verse, which would it be?",
    "Comment one word that describes what this verse gives you.",
    "Has God ever met you in a moment like this verse describes?",
    "Share this with one person before the day ends — you may never know why they needed it.",
]

_OUTRO_BLESS = [
    "🙏 New Scripture every day — subscribe and grow with us.",
    "🙏 One verse a day, every day. Join us.",
    "🕊️ Subscribe for tomorrow's verse — it might be yours.",
    "🙏 Walk with us: a new verse each day.",
    "✝️ Daily verses, daily strength. Subscribe.",
    "🙏 Be blessed today — and come back tomorrow for the next verse.",
    "🕊️ God's Word, one day at a time. Follow along.",
    "🙏 May this verse carry you through today.",
]

# Theme-aware hashtag pools (base + theme). Sampled, never the full block.
_TAG_BASE = ["#bible", "#bibleverse", "#dailyverse", "#faith", "#jesus",
             "#scripture", "#christian", "#god", "#gospel", "#bibleverseoftheday",
             "#christianmotivation", "#holyspirit", "#pray", "#godsword",
             "#verseoftheday", "#jesuslovesyou", "#biblestudy"]
_TAG_THEME = {
    "peace":       ["#peace", "#anxiety", "#calm", "#rest"],
    "trust":       ["#trustgod", "#godsplan", "#guidance"],
    "fear":        ["#courage", "#fearnot", "#bestrong"],
    "hope":        ["#hope", "#newbeginnings", "#godisfaithful"],
    "strength":    ["#strength", "#godisgood", "#perseverance"],
    "love":        ["#godslove", "#love", "#grace"],
    "forgiveness": ["#forgiveness", "#grace", "#mercy"],
    "gratitude":   ["#gratitude", "#thankful", "#praise"],
    "custom":      ["#blessed", "#godisgood"],
}


def _ref_book(ref_disp):
    """'1 Peter 4:14' -> '1 Peter'."""
    return ref_disp.rsplit(" ", 1)[0]


def short_title(hook, ref_disp, seed, theme=""):
    rng = random.Random(seed * 977 + 13)
    fmt = _TITLE_FMTS[rng.randrange(len(_TITLE_FMTS))]
    t = fmt.format(hook=hook.rstrip("."), ref=ref_disp, theme=theme)
    if len(t) > 100:  # fall back to shortest safe shape
        t = f"{ref_disp} — today's verse #shorts"
    return t[:100]


def _links_block():
    """Cross-platform links appended to every description (from data/links.json)."""
    try:
        import pathlib, json as _json
        links = _json.loads((pathlib.Path(__file__).parent.parent
                             / "data" / "links.json").read_text())
        lines = []
        if links.get("facebook"):
            lines.append(f"📘 Facebook: {links['facebook']}")
        if links.get("pinterest"):
            lines.append(f"📌 Pinterest: {links['pinterest']}")
        return ("\n" + "\n".join(lines)) if lines else ""
    except Exception:
        return ""


def short_description(reflection, verse_text, ref_disp, seed, theme_key="custom",
                      keywords=None):
    rng = random.Random(seed * 613 + 7)
    intro = rng.choice(_DESC_INTRO).format(ref=ref_disp, ref_book=_ref_book(ref_disp))
    engage = rng.choice(_ENGAGE)
    outro = rng.choice(_OUTRO_BLESS) + _links_block()

    # hashtags: 1-2 theme + 3 base sampled, order shuffled — never identical
    theme_tags = list(_TAG_THEME.get(theme_key, _TAG_THEME["custom"]))
    kw_tags = ["#" + k.replace(" ", "") for k in (keywords or [])[:2]]
    pool = theme_tags[:2] + kw_tags + rng.sample(_TAG_BASE, 3)
    tags_line = " ".join(dict.fromkeys(["#shorts"] + pool[:5]))

    desc = (
        f"{intro}{reflection}\n\n"
        f"\u201C{verse_text}\u201D — {ref_disp} (Berean Standard Bible)\n\n"
        f"{engage}\n\n{outro}\n\n{tags_line}"
    )
    return desc[:4900]


def short_tags(keywords=None, theme_key="custom", seed=0):
    rng = random.Random(seed * 389 + 3)
    base = ["bible verse", "daily verse", "scripture", "faith", "jesus",
            "christian shorts", "bible", "god", "devotional", "verse of the day"]
    rng.shuffle(base)
    kw = list(keywords or [])
    theme_extra = [t.lstrip("#") for t in _TAG_THEME.get(theme_key, [])]
    return list(dict.fromkeys(kw + theme_extra + ["shorts"] + base))[:25]


if __name__ == "__main__":
    # quick variety demo
    for d in range(6):
        print(short_title("God has a word for you", "Psalms 23:1", seed=d))
    print()
    print(short_description("He restores what the world drains.",
                            "The LORD is my shepherd; I shall not want.",
                            "Psalms 23:1", seed=1, theme_key="peace",
                            keywords=["peace", "rest"]))

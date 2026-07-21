#!/usr/bin/env python3
"""Intelligent verse selection from the FULL Bible (31,086 BSB verses).

Guarantees:
- A verse used once is written to data/used_verses.json and NEVER used again.
- Verses are chosen by judgment, not order: scored for theme relevance,
  devotional weight of the book, and narration-friendly length, with a
  seeded shuffle among the best candidates so selection isn't mechanical.
"""
import json, gzip, re, random, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BIBLE_PATH = DATA / "bible.json.gz"
LEDGER_PATH = DATA / "used_verses.json"

# Books weighted by devotional richness (higher = preferred for meditation content)
BOOK_WEIGHT = {
    "Psalms": 3.0, "Proverbs": 2.4, "Isaiah": 2.4, "John": 2.6, "Matthew": 2.4,
    "Romans": 2.4, "Philippians": 2.6, "Ephesians": 2.4, "James": 2.3,
    "1 Peter": 2.3, "1 John": 2.4, "Hebrews": 2.3, "Luke": 2.2, "Mark": 2.0,
    "Colossians": 2.2, "Galatians": 2.1, "2 Corinthians": 2.1, "1 Corinthians": 2.0,
    "Jeremiah": 1.8, "Lamentations": 1.8, "Deuteronomy": 1.6, "Joshua": 1.6,
    "1 Thessalonians": 1.9, "2 Timothy": 1.9, "Micah": 1.7, "Habakkuk": 1.7,
    "Zephaniah": 1.6, "Nahum": 1.3, "Joel": 1.4, "Hosea": 1.4, "Jonah": 1.4,
    "Ecclesiastes": 1.6, "Job": 1.5, "Genesis": 1.4, "Exodus": 1.4,
    "1 Samuel": 1.3, "2 Samuel": 1.3, "1 Kings": 1.2, "2 Kings": 1.2,
    "Revelation": 1.5, "Acts": 1.5, "Daniel": 1.5, "Song of Solomon": 1.0,
}
DEFAULT_WEIGHT = 1.0

# Theme -> scoring keywords (word stems, lowercase). Strong terms count double.
THEME_TERMS = {
    "peace":        (["peace", "still", "calm", "rest", "quiet", "troubled"], ["storm", "afraid", "anxious"]),
    "trust":        (["trust", "lean", "rely", "confidence", "plans", "direct"], ["path", "way", "guide"]),
    "fear":         (["fear", "afraid", "courage", "dismayed", "terror"], ["strong", "with you", "deliver"]),
    "strength":     (["strength", "strong", "weary", "faint", "power", "renew"], ["uphold", "sustain", "rest"]),
    "love":         (["love", "loving", "beloved", "compassion", "lovingkindness"], ["mercy", "everlasting"]),
    "hope":         (["hope", "wait", "morning", "future", "expectation"], ["anchor", "renew", "mercies"]),
    "forgiveness":  (["forgive", "forgiven", "pardon", "cleanse", "confess"], ["mercy", "sin", "wash"]),
    "faith":        (["faith", "believe", "believed", "assurance", "conviction"], ["impossible", "mustard", "please"]),
    "prayer":       (["pray", "prayer", "call", "ask", "seek", "knock"], ["hear", "answer", "intercede"]),
    "gratitude":    (["thank", "thanksgiving", "praise", "rejoice", "grateful"], ["bless", "sing", "glad"]),
    "guidance":     (["shepherd", "lead", "guide", "path", "lamp", "light"], ["feet", "way", "walk"]),
    "wisdom":       (["wisdom", "wise", "understanding", "discern", "knowledge"], ["fool", "instruct", "counsel"]),
    "identity":     (["child", "children", "chosen", "created", "workmanship", "new creation"], ["belong", "adopted", "royal"]),
    "patience":     (["wait", "patience", "patient", "endure", "season", "appointed"], ["harvest", "due", "perseverance"]),
    "joy":          (["joy", "rejoice", "glad", "delight", "sing"], ["fullness", "morning", "strength"]),
    "healing":      (["heal", "brokenhearted", "wounds", "binds", "comfort", "mourn"], ["restore", "tears", "weep"]),
    "kindness":     (["love one another", "kind", "kindness", "serve", "honor", "neighbor"], ["gentle", "bear", "forgive"]),
    "temptation":   (["tempt", "temptation", "resist", "flee", "escape", "watch"], ["deliver", "evil", "stand"]),
    "scripture":    (["word", "law", "commandment", "precepts", "statutes", "scripture"], ["meditate", "lamp", "sword"]),
    "contentment":  (["content", "enough", "portion", "gain", "godliness"], ["rich", "money", "possessions"]),
    "presence":     (["with you", "presence", "never leave", "forsake", "near"], ["dwell", "abide", "midst"]),
    "purpose":      (["works", "purpose", "called", "calling", "serve", "gift"], ["prepared", "glorify", "light"]),
    "mind":         (["mind", "think", "thoughts", "renew", "meditate"], ["transform", "captive", "stayed"]),
    "generosity":   (["give", "giver", "generous", "sow", "reap", "measure"], ["cheerful", "abound", "poor"]),
    "obedience":    (["obey", "obedience", "keep", "commandments", "do", "hear"], ["observe", "walk", "voice"]),
    "provision":    (["provide", "supply", "need", "bread", "feed", "riches"], ["birds", "lilies", "portion"]),
    "humility":     (["humble", "humility", "lowly", "meek", "pride", "proud"], ["exalt", "grace", "bow"]),
    "light":        (["light", "darkness", "shine", "lamp", "dawn"], ["overcome", "world", "glory"]),
    "endurance":    (["endure", "run", "race", "persevere", "steadfast", "finish"], ["crown", "goal", "faint"]),
    "salvation":    (["salvation", "saved", "cross", "redeem", "gospel", "eternal life"], ["believe", "grace", "blood"]),
    "abiding":      (["abide", "remain", "vine", "branch", "fruit", "dwell"], ["planted", "rooted", "spirit"]),
}

_EXCLUDE = re.compile(
    r"(begat|the son of [A-Z]|genealog|cubits?\b|shekels?\b|leprous|leprosy|"
    r"burnt offering|grain offering|tribe of|clans of|census|numbered)", re.I)

# Harsh / judgment-context wording that reads oddly in a calm devotional
_HARSH = re.compile(
    r"(woe to|wrath|slain|slaughter|labor pains|woman in labor|gnashing|"
    r"vengeance|destroy(?:ed)? the|corpses?|dung|prostitut|adulter|"
    r"swords?\b|spears?\b|the wicked are|no peace.{0,20}wicked|famine|plague|"
    r"pestilence|devour|kill(?:ed)?\b|blood of|curse[ds]?\b|"
    r"deceit|schemes?\b|do not speak|hate[ds]?\b|enemies|enemy\b|betray|"
    r"perish|destruction|hypocrite|serpent|viper|demons?\b|unclean spirit)", re.I)

def load_bible():
    with gzip.open(BIBLE_PATH, "rt", encoding="utf-8") as f:
        return json.load(f)

def load_ledger():
    if LEDGER_PATH.exists():
        return set(json.loads(LEDGER_PATH.read_text())["used"])
    return set()

def save_ledger(used):
    LEDGER_PATH.write_text(json.dumps({"used": sorted(used)}, indent=0))

def _score(text, book, strong, weak):
    t = text.lower()
    s = 0.0
    for w in strong:
        if w in t:
            s += 2.0
    for w in weak:
        if w in t:
            s += 1.0
    if s == 0:
        return 0.0
    s *= BOOK_WEIGHT.get(book, DEFAULT_WEIGHT)
    n = len(text)
    if 70 <= n <= 300:      # ideal narration length
        s *= 1.5
    elif n < 40 or n > 420: # too short/long to carry a segment
        s *= 0.4
    if _EXCLUDE.search(text) or _HARSH.search(text):
        return 0.0  # hard exclude: never devotional material
    return s

# --- Complete-thought detection -------------------------------------------
# A verse must not start or end mid-sentence. If it does, expand to the
# neighbouring verses until the passage is a complete thought (max 3 verses).
_TERMINAL_END = re.compile(r'[.!?][\u201d\u2019"\'\)\]]*\s*$')
_MIDSENTENCE_START = re.compile(r'^[\u201c\u2018"\'\(\[]*[a-z]')

def _ends_complete(text):
    return bool(_TERMINAL_END.search(text.strip()))

def _starts_complete(text):
    return not _MIDSENTENCE_START.match(text.strip())

def _expand_to_thought(bible, ref, used, max_verses=3, max_chars=520):
    """Grow a verse backward/forward until it is a complete thought.
    Returns (all_refs, combined_text, display_ref) or None if impossible
    (crosses chapter, too long, or touches an already-used verse)."""
    book_ch, vn = ref.rsplit(":", 1)
    book, ch = book_ch.rsplit(" ", 1)
    verses = bible[book][ch]
    lo = hi = int(vn)
    # backward: the passage must not open mid-sentence
    while not _starts_complete(verses[str(lo)]):
        if str(lo - 1) not in verses or hi - lo + 1 >= max_verses:
            return None
        lo -= 1
    # forward: the passage must not end hanging
    while not _ends_complete(verses[str(hi)]):
        if str(hi + 1) not in verses or hi - lo + 1 >= max_verses:
            return None
        hi += 1
    refs = [f"{book} {ch}:{i}" for i in range(lo, hi + 1)]
    if any(r in used for r in refs):
        return None
    combined = " ".join(verses[str(i)].strip() for i in range(lo, hi + 1))
    if len(combined) > max_chars or _EXCLUDE.search(combined) or _HARSH.search(combined):
        return None
    disp = refs[0] if lo == hi else f"{book} {ch}:{lo}-{hi}"
    return refs, combined, disp

def pick_verses(theme_key, n, seed, used=None, bible=None):
    """Pick n distinct never-used COMPLETE-THOUGHT passages for a theme.
    Each item: {"ref": display ref (may be a range), "refs": [every verse
    burned], "text": full passage}. Returns (picked, updated used-set);
    the ledger is NOT saved here — the caller saves it."""
    bible = bible or load_bible()
    used = used if used is not None else load_ledger()
    strong, weak = THEME_TERMS[theme_key]

    candidates = []
    for book, chapters in bible.items():
        for ch, verses in chapters.items():
            for vn, text in verses.items():
                ref = f"{book} {ch}:{vn}"
                if ref in used:
                    continue
                sc = _score(text, book, strong, weak)
                if sc > 0:
                    candidates.append((sc, ref, text))
    candidates.sort(key=lambda x: -x[0])
    pool = candidates[:120]  # judgment pool: the 120 most fitting fresh verses
    rng = random.Random(seed)
    rng.shuffle(pool)
    # greedy pick with book diversity (max 2 per book per day)
    picked, per_book, taken = [], {}, set()
    for sc, ref, text in sorted(pool, key=lambda x: -x[0]):
        book = ref.rsplit(" ", 1)[0]
        if per_book.get(book, 0) >= 2:
            continue
        # small seeded jitter so the same theme picks differently across cycles
        if rng.random() < 0.25 and len(pool) - len(picked) > n * 3:
            continue
        exp = _expand_to_thought(bible, ref, used | taken)
        if exp is None:
            continue  # can't form a complete thought — skip this candidate
        refs, full_text, disp = exp
        picked.append({"ref": disp, "refs": refs, "text": full_text})
        taken.update(refs)
        per_book[book] = per_book.get(book, 0) + 1
        if len(picked) == n:
            break
    used.update(taken)
    return picked, used

# Day 1..31 of the plan -> theme key (aligned with data/plan.json order)
THEME_KEYS = ["peace", "trust", "fear", "strength", "love", "hope", "forgiveness",
              "faith", "prayer", "gratitude", "guidance", "wisdom", "identity",
              "patience", "joy", "healing", "kindness", "temptation", "scripture",
              "contentment", "presence", "purpose", "mind", "generosity", "obedience",
              "provision", "humility", "light", "endurance", "salvation", "abiding"]

def theme_for_day(day):
    return THEME_KEYS[(day - 1) % len(THEME_KEYS)]

def pick_for_episode(day, cycle, plan_days=31):
    """Deterministic selection for one episode: 5 long-form verses + 1 Short
    verse, all never used before, no overlap. Deterministic per episode so
    build_longform / build_short / daily.py all agree without coordination.
    Ledger is NOT saved here — daily.py saves it only after success."""
    ep = (cycle - 1) * plan_days + day
    theme = theme_for_day(day)
    used = load_ledger()
    bible = load_bible()
    picked, used = pick_verses(theme, 6, seed=ep * 977 + 13, used=used, bible=bible)
    # Safety net: if a theme's fresh pool ever runs dry (years out), top up
    # from neighbouring themes so the channel never misses a day.
    ti = THEME_KEYS.index(theme)
    while len(picked) < 6:
        ti = (ti + 1) % len(THEME_KEYS)
        extra, used = pick_verses(THEME_KEYS[ti], 6 - len(picked),
                                  seed=ep * 977 + 13 + ti, used=used, bible=bible)
        if not extra:
            continue
        picked.extend(extra)
    return {"theme_key": theme, "episode": ep,
            "longform": picked[:5], "short": picked[5], "used": used}

# ---------------------------------------------------------------------------
# Reflection composer: turns any picked verse into a short devotional
# reflection, in the same voice as the original plan reflections.
# ---------------------------------------------------------------------------
THEME_APP = {
    "peace":       ("when anxiety rises and life feels loud",
                    ["let this promise slow your breathing and quiet your heart",
                     "hand God the one thing that is stealing your peace right now",
                     "choose stillness over striving, and trust Him with what you cannot control"]),
    "trust":       ("when the road ahead is unclear",
                    ["release your grip on the outcome and lean your full weight on Him",
                     "trade your need to understand for the peace of being led",
                     "take the next small step and trust God with the rest of the path"]),
    "fear":        ("when fear whispers that you are alone",
                    ["remember that courage is not the absence of fear, but the presence of God",
                     "speak this truth out loud over the thing that frightens you",
                     "step forward anyway — the One who goes with you has never lost a battle"]),
    "strength":    ("when you are running on empty",
                    ["stop trying to be strong alone and let God carry what you cannot",
                     "bring your exhaustion to Him honestly — His strength begins where yours ends",
                     "rest is not weakness; it is trust in the One who renews the weary"]),
    "love":        ("when you wonder if you are truly loved",
                    ["let this settle deep: God's love for you was never based on your performance",
                     "receive His love before you try to earn it — it was always a gift",
                     "you are not loved because you are valuable; you are valuable because you are loved"]),
    "hope":        ("when the night feels long",
                    ["hold on — God writes His best chapters in the dark",
                     "anchor your hope not in circumstances changing, but in a God who never does",
                     "morning is coming, and the One who promised it keeps His word"]),
    "forgiveness": ("when guilt keeps replaying your past",
                    ["what God has forgiven, you are free to stop carrying",
                     "come to Him honestly — mercy is waiting, not a lecture",
                     "let grace have the final word over your worst moment"]),
    "faith":       ("when believing feels hard",
                    ["faith is not a feeling; it is a decision to trust God's character",
                     "bring your small faith to a great God — He does the impossible part",
                     "walk by what God has said, not by what your eyes can see today"]),
    "prayer":      ("when heaven feels silent",
                    ["keep asking — persistence in prayer is faith refusing to let go",
                     "God is not annoyed by your prayers; He is drawn to them",
                     "prayer doesn't just change circumstances — it changes the one who prays"]),
    "gratitude":   ("when it's easier to count what's missing",
                    ["name three gifts from today out loud — gratitude rewires the heart",
                     "thanksgiving is the doorway into God's presence; walk through it now",
                     "a grateful heart sees the same life through completely different eyes"]),
    "guidance":    ("when you don't know which way to go",
                    ["the Shepherd doesn't just point the way — He walks it with you",
                     "follow one step of obedience today and the path will keep appearing",
                     "you don't need the whole map when you know the Guide"]),
    "wisdom":      ("when a decision weighs on you",
                    ["ask God for wisdom first, not last — He gives generously",
                     "true wisdom begins with trusting God more than your own analysis",
                     "let His Word, not the loudest voice around you, shape your choice"]),
    "identity":    ("when you forget who you are",
                    ["your identity is not what you do — it is whose you are",
                     "let God's opinion of you outweigh every other voice today",
                     "you were chosen on purpose, for a purpose, before you did anything at all"]),
    "patience":    ("when God's timing feels slow",
                    ["what feels like a delay is often God working deep beneath the surface",
                     "waiting is not wasted time when you wait with God",
                     "trust the Gardener — fruit that lasts is never rushed"]),
    "joy":         ("when circumstances give you no reason to smile",
                    ["joy is not denial of pain — it is confidence in a God who is bigger than it",
                     "God's joy is your strength precisely on the days you feel weakest",
                     "rejoice on purpose today, and watch your perspective follow"]),
    "healing":     ("when your heart carries wounds no one sees",
                    ["God is not distant from your pain — He is closest right there",
                     "bring Him the broken pieces; He binds up what others walked past",
                     "healing begins the moment you stop hiding the wound from Him"]),
    "kindness":    ("when loving people feels costly",
                    ["love the person in front of you today the way God loved you first",
                     "kindness is never wasted — it is planted, and it grows",
                     "let someone experience God's gentleness through your hands today"]),
    "temptation":  ("when temptation feels stronger than you",
                    ["you are never trapped — God always builds a way of escape; look for it",
                     "flee early; the battle is won at the first step, not the last",
                     "lean on His strength in the moment of weakness — that's what it's for"]),
    "scripture":   ("when your soul feels undernourished",
                    ["read one verse slowly today and let it read you back",
                     "God's Word is daily bread — a feast once a week is not enough",
                     "hide this verse in your heart; you will need it sooner than you think"]),
    "contentment": ("when comparison steals your gratitude",
                    ["contentment is not having everything — it is knowing you have Him",
                     "stop measuring your life against someone else's highlight reel",
                     "godliness with contentment is the wealth no market can touch"]),
    "presence":    ("when loneliness closes in",
                    ["you may feel alone, but you have never once been alone",
                     "practice His presence today — He is nearer than your next breath",
                     "the God who counts the stars knows exactly where you are tonight"]),
    "purpose":     ("when your days feel small and unseen",
                    ["no act of faithfulness is invisible to God",
                     "you were created for good works prepared before you were born — walk in them today",
                     "serve where you are planted; God turns ordinary obedience into eternal impact"]),
    "mind":        ("when your thoughts spiral",
                    ["take that anxious thought captive and hand it to Christ",
                     "peace guards the mind that stays fixed on Him — return your gaze there now",
                     "you cannot stop birds flying overhead, but you can stop them nesting; choose your thoughts"]),
    "generosity":  ("when holding tight feels safer than giving",
                    ["give something away today — generosity breaks fear's grip on the heart",
                     "you can never out-give God; the open hand is always the fuller one",
                     "what you release into God's hands multiplies; what you clutch, withers"]),
    "obedience":   ("when obeying God costs something",
                    ["delayed obedience is a heavy backpack — set it down and simply do the next right thing",
                     "obedience is trust with work boots on",
                     "God's commands are not fences to cage you but rails to protect you"]),
    "provision":   ("when the numbers don't add up",
                    ["the God who feeds the birds has not forgotten your name",
                     "bring Him the little you have — provision often starts with surrender",
                     "seek Him first today and watch the 'everything else' fall into place"]),
    "humility":    ("when pride wants the credit",
                    ["the way up in God's kingdom has always been down",
                     "humility is not thinking less of yourself — it is thinking of yourself less",
                     "bow low today; God gives grace to the humble and lifts them at the right time"]),
    "light":       ("when darkness feels like it's winning",
                    ["light does not negotiate with darkness — it simply shines; so shine",
                     "carry His light into one dark place today: a room, a conversation, a heart",
                     "the darkness has never once overcome His light, and it won't start with you"]),
    "endurance":   ("when you're tempted to quit",
                    ["run today's mile, not the whole race — grace comes one day at a time",
                     "fix your eyes on Jesus, not the finish line's distance",
                     "the crown goes not to the fastest but to the faithful — keep going"]),
    "salvation":   ("when you wonder if grace is really for you",
                    ["the cross was not a gesture — it was a rescue, and it was for you",
                     "you don't clean yourself up to come to God; you come, and He makes you new",
                     "let the empty tomb remind you: nothing about your story is beyond redemption"]),
    "abiding":     ("when you're tempted to run on your own strength",
                    ["stay connected to the Vine today — five quiet minutes with Him changes everything",
                     "fruit is not produced by trying harder but by abiding closer",
                     "make your home in His presence, and let Him make His home in you"]),
}

_TEMPLATES = [
    'Hear the heart of this verse: "{phrase}" {situation_cap}, God\'s Word does not offer a technique — it offers Himself. Today, {app}.',
    'Notice what God is saying here: "{phrase}" {situation_cap}, this is the truth to stand on. Today, {app}.',
    'Let these words sink in: "{phrase}" {situation_cap}, Scripture meets you exactly where you are. Today, {app}.',
    'This is not just poetry — it is a promise: "{phrase}" {situation_cap}, hold onto it. Today, {app}.',
    'God speaks directly to you in this verse: "{phrase}" {situation_cap}, receive it as spoken over your life. Today, {app}.',
]

def _key_phrase(text, max_len=90):
    """A natural quotable phrase from the verse: first clause or sentence."""
    for stop in [". ", "; ", ", "]:
        i = text.find(stop)
        if 25 <= i <= max_len:
            return text[:i + 1].strip().rstrip(",;") + ("." if text[i] != "." else "")
    if len(text) <= max_len:
        return text.strip()
    cut = text[:max_len].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "..."

def reflect(verse, theme_key, seed):
    """Compose a devotional reflection for a dynamically-picked verse."""
    situation, apps = THEME_APP[theme_key]
    rng = random.Random(seed)
    tpl = rng.choice(_TEMPLATES)
    return tpl.format(phrase=_key_phrase(verse["text"]),
                      situation_cap=situation[0].upper() + situation[1:],
                      app=rng.choice(apps))

def reflect_short(verse, theme_key, seed):
    """Punchier one-liner reflection for Shorts (verse was just read aloud)."""
    situation, apps = THEME_APP[theme_key]
    rng = random.Random(seed)
    app = rng.choice(apps)
    return f"{situation[0].upper() + situation[1:]}, this is God's word for you. Today, {app}."

def pick_for_shorts(day, cycle, count=2, plan_days=31):
    """Shorts-only mode: pick `count` fresh verses for the day's Shorts.
    Deterministic per episode; ledger NOT saved here (daily.py saves it)."""
    ep = (cycle - 1) * plan_days + day
    theme = theme_for_day(day)
    used = load_ledger()
    bible = load_bible()
    picked, used = pick_verses(theme, count, seed=ep * 977 + 411, used=used, bible=bible)
    ti = THEME_KEYS.index(theme)
    while len(picked) < count:  # dry-pool safety net
        ti = (ti + 1) % len(THEME_KEYS)
        extra, used = pick_verses(THEME_KEYS[ti], count - len(picked),
                                  seed=ep * 977 + 411 + ti, used=used, bible=bible)
        if extra:
            picked.extend(extra)
    return {"theme_key": theme, "episode": ep, "verses": picked, "used": used}

_HOOK_TPL = [
    "Stop scrolling. This verse is for you.",
    "God has a word for you {situation}.",
    "If today feels heavy, hear this.",
    "You needed to see this verse today.",
    "Before you keep scrolling — 30 seconds with God's Word.",
    "This one verse can change your whole day.",
    "Read this before the day gets loud.",
    "Heaven has a message for you today.",
]

def hook_for(theme_key, seed):
    situation, _ = THEME_APP[theme_key]
    rng = random.Random(seed)
    return rng.choice(_HOOK_TPL).format(situation=situation)

if __name__ == "__main__":
    used = load_ledger()
    b = load_bible()
    total = sum(len(v) for chs in b.values() for v in chs.values())
    print(f"Bible: {total} verses | used so far: {len(used)}")
    sel = pick_for_episode(day=1, cycle=1)
    print(f"\nEpisode {sel['episode']} ({sel['theme_key']}):")
    for i, p in enumerate(sel["longform"], 1):
        print(f"  LF{i} {p['ref']}: {p['text'][:70]}")
        print(f"       -> {reflect(p, sel['theme_key'], seed=sel['episode']*31+i)[:110]}")
    print(f"  SHORT {sel['short']['ref']}: {sel['short']['text'][:70]}")

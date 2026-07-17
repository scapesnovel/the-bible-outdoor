#!/usr/bin/env python3
"""Generate a bold clickable thumbnail (1280x720) for the long-form video."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import ASSETS, OUT, CHANNEL_NAME, get_day_entry
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
from text_render import FONT_SERIF_BOLD, FONT_SERIF_ITALIC, _wrap

W, H = 1280, 720
GOLD = (240, 200, 110)
CREAM = (250, 246, 236)

def build(day_number=None):
    plan, entry, day_number = get_day_entry(day_number)
    final_dir = OUT / f"day{day_number:02d}"
    final_dir.mkdir(parents=True, exist_ok=True)

    bgs = sorted((ASSETS / "backgrounds").glob("*.jpg"))
    bg = Image.open(bgs[(day_number - 1) % len(bgs)]).convert("RGB")
    # cover-crop to 1280x720
    ratio = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * ratio) + 1, int(bg.height * ratio) + 1))
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2,
                  (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = ImageEnhance.Brightness(bg).enhance(0.72)
    bg = ImageEnhance.Contrast(bg).enhance(1.12)

    # left dark gradient for text
    grad = Image.new("L", (W, 1), 0)
    for x in range(W):
        grad.putpixel((x, 0), max(0, 170 - int(x / W * 260)))
    grad = grad.resize((W, H))
    black = Image.new("RGB", (W, H), (5, 10, 16))
    bg = Image.composite(black, bg, grad)

    d = ImageDraw.Draw(bg)
    theme = entry["theme"].upper()
    f_big = ImageFont.truetype(FONT_SERIF_BOLD, 108)
    lines = _wrap(d, theme, f_big, int(W * 0.62))
    while len(lines) > 3:
        f_big = ImageFont.truetype(FONT_SERIF_BOLD, f_big.size - 8)
        lines = _wrap(d, theme, f_big, int(W * 0.62))
    lh = int(f_big.size * 1.12)
    total = len(lines) * lh
    y = (H - total) // 2 - 30
    for ln in lines:
        d.text((66, y + 5), ln, font=f_big, fill=(0, 0, 0))
        d.text((60, y), ln, font=f_big, fill=GOLD)
        y += lh

    f_sub = ImageFont.truetype(FONT_SERIF_ITALIC, 44)
    sub = "5 Verses + Guided Prayer"
    d.text((63, y + 18), sub, font=f_sub, fill=(0, 0, 0))
    d.text((60, y + 15), sub, font=f_sub, fill=CREAM)

    # gold accent bar + channel tag
    d.rectangle([60, y + 80, 60 + 340, y + 86], fill=GOLD)
    f_tag = ImageFont.truetype(FONT_SERIF_BOLD, 34)
    d.text((60, y + 100), CHANNEL_NAME.upper(), font=f_tag, fill=CREAM)

    # logo bottom-right
    logo_p = ASSETS / "brand" / "logo.png"
    if logo_p.exists():
        logo = Image.open(logo_p).convert("RGBA").resize((150, 150))
        bg.paste(logo, (W - 175, H - 175), logo)

    out = final_dir / f"day{day_number:02d}_thumbnail.jpg"
    bg.save(out, quality=90)
    print(f"THUMBNAIL day {day_number}: {out}")
    return out

if __name__ == "__main__":
    day = int(sys.argv[1]) if len(sys.argv) > 1 else None
    build(day)

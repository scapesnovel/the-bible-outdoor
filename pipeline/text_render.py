#!/usr/bin/env python3
"""Render verse text overlay cards (transparent PNGs) with PIL."""
from PIL import Image, ImageDraw, ImageFont
import textwrap

import os

def _first_existing(*paths):
    for p in paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"No usable font among: {paths}")

FONT_SERIF_BOLD = _first_existing(
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf")
FONT_SERIF = _first_existing(
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf")
FONT_SERIF_ITALIC = _first_existing(
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")

GOLD = (232, 197, 116, 255)
CREAM = (248, 244, 234, 255)
SOFT = (226, 226, 220, 255)

def _wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines

def _fit_font(draw, text, path, max_w, max_h, start=64, minimum=28, spacing_mult=1.35):
    size = start
    while size >= minimum:
        font = ImageFont.truetype(path, size)
        lines = _wrap(draw, text, font, max_w)
        h = len(lines) * int(size * spacing_mult)
        if h <= max_h:
            return font, lines, int(size * spacing_mult)
        size -= 4
    font = ImageFont.truetype(path, minimum)
    return font, _wrap(draw, text, font, max_w), int(minimum * spacing_mult)

def _draw_center(draw, lines, font, line_h, cx, y, fill, shadow=True):
    for ln in lines:
        w = draw.textlength(ln, font=font)
        x = cx - w / 2
        if shadow:
            draw.text((x + 3, y + 3), ln, font=font, fill=(0, 0, 0, 200))
        draw.text((x, y), ln, font=font, fill=fill)
        y += line_h
    return y

def make_card(width, height, title=None, body=None, ref=None, body_start=64,
              title_size=54, ref_size=40, margin_ratio=0.10, out_path=None):
    """Generic centered text card on transparent bg with dark scrim."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # dark scrim for readability
    scrim = Image.new("RGBA", (width, height), (10, 15, 20, 128))
    img.alpha_composite(scrim)

    margin = int(width * margin_ratio)
    max_w = width - 2 * margin
    cx = width // 2

    blocks = []
    if title:
        f = ImageFont.truetype(FONT_SERIF_BOLD, title_size)
        lines = _wrap(d, title, f, max_w)
        blocks.append(("title", f, lines, int(title_size * 1.3)))
    if body:
        f, lines, lh = _fit_font(d, body, FONT_SERIF, max_w, int(height * 0.55), start=body_start)
        blocks.append(("body", f, lines, lh))
    if ref:
        f = ImageFont.truetype(FONT_SERIF_ITALIC, ref_size)
        lines = _wrap(d, ref, f, max_w)
        blocks.append(("ref", f, lines, int(ref_size * 1.35)))

    total_h = sum(len(l) * lh for _, _, l, lh in blocks) + (len(blocks) - 1) * int(height * 0.04)
    y = (height - total_h) // 2
    for kind, f, lines, lh in blocks:
        color = GOLD if kind in ("title", "ref") else CREAM
        y = _draw_center(d, lines, f, lh, cx, y, color)
        y += int(height * 0.04)

    if out_path:
        img.save(out_path)
    return img

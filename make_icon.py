#!/usr/bin/env python3
"""Genera assets/icon.icns: squircle rojo con nota musical blanca."""
import os
import math
import subprocess
from PIL import Image, ImageDraw, ImageFont

S = 1024
OUT = "assets"
os.makedirs(OUT, exist_ok=True)


def squircle_mask(size, n=4.0):
    """Mascara de superellipse (squircle estilo macOS)."""
    m = Image.new("L", (size, size), 0)
    px = m.load()
    c = (size - 1) / 2.0
    r = size / 2.0
    for y in range(size):
        for x in range(size):
            dx = abs(x - c) / r
            dy = abs(y - c) / r
            if dx ** n + dy ** n <= 1.0:
                px[x, y] = 255
    return m


def vgradient(size, top, bottom):
    g = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(g)
    for y in range(size):
        t = y / (size - 1)
        col = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (size, y)], fill=col)
    return g


def load_font(size):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Apple Symbols.ttf",
        "/System/Library/Fonts/Symbol.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


# --- base: gradiente rojo recortado a squircle ---
base = vgradient(S, (0xF8, 0x55, 0x4B), (0xCE, 0x26, 0x1F)).convert("RGBA")
mask = squircle_mask(S, n=4.0)
icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
icon.paste(base, (0, 0), mask)

draw = ImageDraw.Draw(icon)

# brillo superior sutil
gloss = Image.new("L", (S, S), 0)
gd = ImageDraw.Draw(gloss)
gd.ellipse([-S * 0.3, -S * 0.75, S * 1.3, S * 0.35], fill=70)
white = Image.new("RGBA", (S, S), (255, 255, 255, 255))
icon = Image.composite(white, icon, Image.composite(gloss, Image.new("L", (S, S), 0), mask))
draw = ImageDraw.Draw(icon)

# nota musical blanca centrada con sombra
glyph = "♫"  # ♫
font = load_font(560)
bbox = draw.textbbox((0, 0), glyph, font=font)
gw, gh = bbox[2] - bbox[0], bbox[3] - bbox[1]
gx = (S - gw) / 2 - bbox[0]
gy = (S - gh) / 2 - bbox[1] - S * 0.02
draw.text((gx + 8, gy + 10), glyph, font=font, fill=(120, 10, 6, 90))   # sombra
draw.text((gx, gy), glyph, font=font, fill=(255, 255, 255, 255))         # nota

icon.save(os.path.join(OUT, "icon_1024.png"))

# --- iconset multi-tamano + .icns ---
iconset = os.path.join(OUT, "icon.iconset")
os.makedirs(iconset, exist_ok=True)
sizes = [16, 32, 64, 128, 256, 512, 1024]
for s in sizes:
    img = icon.resize((s, s), Image.LANCZOS)
    img.save(os.path.join(iconset, "icon_%dx%d.png" % (s, s)))
    if s <= 512:
        img2 = icon.resize((s * 2, s * 2), Image.LANCZOS)
        img2.save(os.path.join(iconset, "icon_%dx%d@2x.png" % (s, s)))

subprocess.run(["iconutil", "-c", "icns", iconset,
                "-o", os.path.join(OUT, "icon.icns")], check=True)
print("icono creado:", os.path.join(OUT, "icon.icns"))

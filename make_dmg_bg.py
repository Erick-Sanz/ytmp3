#!/usr/bin/env python3
"""Genera assets/dmg_bg.png: fondo de la ventana del instalador."""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 660, 420
OUT = "assets"
os.makedirs(OUT, exist_ok=True)


def font(path_list, size):
    for p in path_list:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


HEL = ["/System/Library/Fonts/HelveticaNeue.ttc",
       "/System/Library/Fonts/Helvetica.ttc"]

# fondo: gradiente vertical muy claro
img = Image.new("RGB", (W, H))
d = ImageDraw.Draw(img)
top, bot = (0xFB, 0xFB, 0xFD), (0xEC, 0xEE, 0xF2)
for y in range(H):
    t = y / (H - 1)
    d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t)
                                        for i in range(3)))

# banda superior roja sutil
d.rectangle([0, 0, W, 6], fill=(0xE2, 0x3B, 0x34))

# titulo
f_title = font(HEL, 30)
f_sub = font(HEL, 15)
d.text((W / 2, 52), "ytmp3", font=f_title, fill=(0x1D, 0x1F, 0x24), anchor="mm")
d.text((W / 2, 84), "Descargador de musica de YouTube",
       font=f_sub, fill=(0x5B, 0x60, 0x68), anchor="mm")

# flecha de app -> Aplicaciones (centro vertical donde van los iconos)
ay = 232
x0, x1 = 268, 392
d.line([(x0, ay), (x1, ay)], fill=(0xB6, 0xBb, 0xC2), width=6)
d.polygon([(x1, ay - 16), (x1 + 26, ay), (x1, ay + 16)], fill=(0xB6, 0xBb, 0xC2))

# instruccion inferior
f_hint = font(HEL, 14)
d.text((W / 2, 352),
       "Arrastra  ytmp3  a  la  carpeta  Aplicaciones",
       font=f_hint, fill=(0x5B, 0x60, 0x68), anchor="mm")

img.save(os.path.join(OUT, "dmg_bg.png"))

# version @2x para pantallas retina
img.resize((W * 2, H * 2), Image.LANCZOS).save(os.path.join(OUT, "dmg_bg@2x.png"))
print("fondo creado:", os.path.join(OUT, "dmg_bg.png"))

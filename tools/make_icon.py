#!/usr/bin/env python3
"""Génère l'icône de l'application : scdl.icns (macOS) et scdl.ico (Windows).

    python tools/make_icon.py

Le dessin est fait par code — pas d'image binaire à traîner dans le dépôt, et
l'icône se régénère à l'identique. Motif : une flèche descendante posée sur un
égaliseur, sur un dégradé violet. Volontairement éloigné des couleurs et du
logo de SoundCloud, qui sont leur marque.

Prérequis : pip install pillow
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SIZE = 1024                      # on dessine grand, on réduit ensuite

TOP = (124, 58, 237)             # violet
BOTTOM = (219, 39, 119)          # magenta
INK = (255, 255, 255)


def rounded_gradient(size: int) -> Image.Image:
    """Carré aux coins arrondis, rempli d'un dégradé vertical."""
    gradient = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / max(size - 1, 1)
        gradient.putpixel((0, y), tuple(
            round(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3)))
    gradient = gradient.resize((size, size))

    mask = Image.new("L", (size, size), 0)
    # rayon proche de celui des icônes macOS modernes
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=round(size * 0.225), fill=255)

    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    icon.paste(gradient, (0, 0), mask)
    return icon


def draw_symbol(icon: Image.Image) -> None:
    """Flèche vers le bas au-dessus d'un égaliseur."""
    size = icon.width
    draw = ImageDraw.Draw(icon)
    cx = size / 2

    # hampe de la flèche
    stem_w = size * 0.085
    stem_top = size * 0.185
    stem_bottom = size * 0.435
    draw.rounded_rectangle(
        (cx - stem_w / 2, stem_top, cx + stem_w / 2, stem_bottom),
        radius=stem_w / 2, fill=INK)

    # pointe : triangle aux angles adoucis par un contour épais
    half = size * 0.155
    tip_y = size * 0.565
    top_y = size * 0.395
    draw.polygon([(cx - half, top_y), (cx + half, top_y), (cx, tip_y)],
                 fill=INK, outline=INK, width=round(size * 0.035))

    # égaliseur : barres franches, base commune, hauteurs contrastées
    heights = [0.105, 0.180, 0.130, 0.215, 0.090]
    bar_w = size * 0.062
    gap = size * 0.036
    total = len(heights) * bar_w + (len(heights) - 1) * gap
    x = cx - total / 2
    base = size * 0.805
    for h in heights:
        top = base - size * h
        draw.rounded_rectangle((x, top, x + bar_w, base),
                               radius=bar_w / 2, fill=INK)
        x += bar_w + gap


def build_icon() -> Image.Image:
    icon = rounded_gradient(SIZE)
    draw_symbol(icon)
    return icon


def write_icns(icon: Image.Image, destination: Path) -> bool:
    """iconutil n'existe que sur macOS ; ailleurs on saute proprement."""
    if sys.platform != "darwin" or not shutil.which("iconutil"):
        return False
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "scdl.iconset"
        iconset.mkdir()
        for base in (16, 32, 128, 256, 512):
            icon.resize((base, base), Image.LANCZOS).save(iconset / f"icon_{base}x{base}.png")
            icon.resize((base * 2, base * 2), Image.LANCZOS).save(
                iconset / f"icon_{base}x{base}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(destination)],
                       check=True)
    return True


def main() -> int:
    icon = build_icon()

    png = ROOT / "docs" / "icon.png"
    png.parent.mkdir(exist_ok=True)
    icon.resize((512, 512), Image.LANCZOS).save(png)
    print(f"ecrit {png.relative_to(ROOT)}")

    # Version d'en-tête : tkinter ne sait réduire que par facteurs entiers,
    # on lui fournit donc directement la bonne taille.
    header = ROOT / "icon-64.png"
    icon.resize((64, 64), Image.LANCZOS).save(header)
    print(f"ecrit {header.relative_to(ROOT)}")

    ico = ROOT / "scdl.ico"
    icon.save(ico, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print(f"ecrit {ico.relative_to(ROOT)}")

    icns = ROOT / "scdl.icns"
    if write_icns(icon, icns):
        print(f"ecrit {icns.relative_to(ROOT)}")
    else:
        print("icns non genere (iconutil absent : normal hors macOS)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

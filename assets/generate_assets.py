"""
Generate the app icon set (placeholder branding).

Renders a card-stack glyph on a rounded indigo tile, then exports:
  - icon.ico               (multi-size, for the PyInstaller exe)
  - Square44x44Logo.png    (taskbar / Store)
  - Square71x71Logo.png
  - Square150x150Logo.png  (medium tile)
  - Square310x310Logo.png  (large tile)
  - Wide310x150Logo.png    (wide tile)
  - StoreLogo.png  (50x50)
  - splash.png     (620x300, optional MSIX splash)

Run:  python assets/generate_assets.py
Swap in real branding later by replacing these files (keep the names).
"""

from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).parent
ACCENT = (88, 101, 242)        # #5865f2 indigo
ACCENT_DK = (60, 70, 190)
WHITE = (255, 255, 255)


def _rounded(size, radius, fill):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=fill)
    return img


def _card(w, h, radius, fill, stripe=None):
    """A white card with optional accent stripe near the bottom."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=fill)
    if stripe:
        sy = int(h * 0.72)
        d.rounded_rectangle([int(w * 0.12), sy, int(w * 0.88), sy + int(h * 0.11)],
                            radius=int(h * 0.04), fill=stripe)
    return img


def render(size: int) -> Image.Image:
    """Render the master icon at the given square size."""
    S = 1024
    base = _rounded(S, radius=int(S * 0.18), fill=ACCENT)
    draw = ImageDraw.Draw(base)
    # subtle darker corner glow (cheap gradient feel)
    draw.ellipse([int(S * 0.45), int(S * 0.45), int(S * 1.2), int(S * 1.2)],
                 fill=ACCENT_DK + (90,))

    # Back card — rotated, slightly smaller, semi-transparent
    cw, ch = int(S * 0.42), int(S * 0.58)
    back = _card(cw, ch, int(cw * 0.10), (255, 255, 255, 150))
    back = back.rotate(14, expand=True, resample=Image.BICUBIC)
    base.alpha_composite(back, (int(S * 0.30), int(S * 0.20)))

    # Front card — upright, with an accent stripe (team-banner vibe)
    front = _card(cw, ch, int(cw * 0.10), WHITE, stripe=ACCENT)
    front = front.rotate(-6, expand=True, resample=Image.BICUBIC)
    base.alpha_composite(front, (int(S * 0.27), int(S * 0.21)))

    if size != S:
        base = base.resize((size, size), Image.LANCZOS)
    return base


def main():
    master = render(1024)

    # Multi-size .ico for the exe
    ico_sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    master.save(OUT / "icon.ico", sizes=ico_sizes)

    # MSIX tile PNGs
    tiles = {
        "Square44x44Logo.png": 44,
        "Square71x71Logo.png": 71,
        "Square150x150Logo.png": 150,
        "Square310x310Logo.png": 310,
        "StoreLogo.png": 50,
    }
    for name, s in tiles.items():
        render(s).save(OUT / name)

    # Wide tile (310x150) — tile on accent with the glyph left-aligned
    wide = Image.new("RGBA", (310, 150), ACCENT + (255,))
    glyph = render(150).resize((120, 120), Image.LANCZOS)
    wide.alpha_composite(glyph, (16, 15))
    wide.save(OUT / "Wide310x150Logo.png")

    # PNG icon for general use
    render(256).save(OUT / "icon.png")

    print("Generated:", ", ".join(sorted(p.name for p in OUT.glob("*.png"))),
          "+ icon.ico")


if __name__ == "__main__":
    main()

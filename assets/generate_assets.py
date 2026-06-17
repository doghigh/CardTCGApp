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


def _font(size: int):
    """Load a bold system font for the wordmark, with fallbacks."""
    from PIL import ImageFont
    for name in ("segoeuib.ttf", "seguisb.ttf", "arialbd.ttf", "calibrib.ttf"):
        try:
            return ImageFont.truetype(rf"C:\Windows\Fonts\{name}", size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wordmark(text="Lorebox", text_color=WHITE, fill=None, glyph_px=200,
              pad=28, gap=22):
    """Horizontal lockup: card glyph + wordmark. Transparent unless `fill`."""
    f = _font(int(glyph_px * 0.62))
    # measure text
    tmp = Image.new("RGBA", (10, 10))
    bbox = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    w = pad + glyph_px + gap + tw + pad
    h = pad + glyph_px + pad
    img = Image.new("RGBA", (w, h), (fill + (255,)) if fill else (0, 0, 0, 0))

    glyph = render(glyph_px)
    img.alpha_composite(glyph, (pad, pad))

    d = ImageDraw.Draw(img)
    ty = (h - th) // 2 - bbox[1]
    d.text((pad + glyph_px + gap, ty), text, font=f, fill=text_color + (255,))
    return img


def _square_with_wordmark(size, text="Lorebox"):
    """Glyph on top + wordmark below, on the accent tile (for big tiles)."""
    img = render(size)  # glyph on rounded accent tile
    d = ImageDraw.Draw(img)
    f = _font(int(size * 0.13))
    bbox = d.textbbox((0, 0), text, font=f)
    tw = bbox[2] - bbox[0]
    # band along the bottom for legibility
    band_h = int(size * 0.26)
    band = Image.new("RGBA", (size, band_h), (0, 0, 0, 90))
    img.alpha_composite(band, (0, size - band_h))
    d.text(((size - tw) // 2 - bbox[0], size - band_h + (band_h - (bbox[3] - bbox[1])) // 2 - bbox[1]),
           text, font=f, fill=WHITE + (255,))
    return img


def main():
    master = render(1024)

    # Multi-size .ico for the exe (glyph only — text is illegible small)
    ico_sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    master.save(OUT / "icon.ico", sizes=ico_sizes)

    # Small square tiles: glyph only (unreadable with text)
    for name, s in {"Square44x44Logo.png": 44, "Square71x71Logo.png": 71,
                    "Square150x150Logo.png": 150, "StoreLogo.png": 50}.items():
        render(s).save(OUT / name)

    # Large square tile (310): glyph + "Lorebox" wordmark band
    _square_with_wordmark(310).save(OUT / "Square310x310Logo.png")

    # Wide tile (310x150): glyph left + "Lorebox" wordmark right, on accent
    wide = Image.new("RGBA", (310, 150), ACCENT + (255,))
    glyph = render(120)
    wide.alpha_composite(glyph, (14, 15))
    d = ImageDraw.Draw(wide)
    f = _font(40)
    bbox = d.textbbox((0, 0), "Lorebox", font=f)
    d.text((150, (150 - (bbox[3] - bbox[1])) // 2 - bbox[1]), "Lorebox",
           font=f, fill=WHITE + (255,))
    wide.save(OUT / "Wide310x150Logo.png")

    # Standalone wordmark lockups (Store promo / website)
    _wordmark().save(OUT / "wordmark.png")                       # transparent
    _wordmark(fill=ACCENT).save(OUT / "wordmark_on_accent.png")  # on indigo

    # PNG icon for general use
    render(256).save(OUT / "icon.png")

    print("Generated:", ", ".join(sorted(p.name for p in OUT.glob("*.png"))),
          "+ icon.ico")


if __name__ == "__main__":
    main()

"""
Accent-color presets (teams, card games) and extract-from-image helper.

Used by the Appearance settings to let users theme the app to a favorite
team's color or a color pulled straight from one of their cards.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Curated accent presets → primary hex color.
# Grouped by a "Category — Name" key so they read nicely in a combo box.
ACCENT_PRESETS = {
    "Default — Indigo": "#5865f2",

    # ── MLB (primary colors) ──
    "MLB — Diamondbacks": "#A71930",
    "MLB — Braves":       "#CE1141",
    "MLB — Orioles":      "#DF4601",
    "MLB — Red Sox":      "#BD3039",
    "MLB — Cubs":         "#0E3386",
    "MLB — Reds":         "#C6011F",
    "MLB — Guardians":    "#00385D",
    "MLB — Rockies":      "#333366",
    "MLB — Tigers":       "#0C2340",
    "MLB — Astros":       "#EB6E1F",
    "MLB — Royals":       "#004687",
    "MLB — Angels":       "#BA0021",
    "MLB — Dodgers":      "#005A9C",
    "MLB — Marlins":      "#00A3E0",
    "MLB — Brewers":      "#12284B",
    "MLB — Twins":        "#002B5C",
    "MLB — Mets":         "#002D72",
    "MLB — Yankees":      "#0C2340",
    "MLB — Athletics":    "#003831",
    "MLB — Phillies":     "#E81828",
    "MLB — Pirates":      "#FDB827",
    "MLB — Padres":       "#2F241D",
    "MLB — Giants":       "#FD5A1E",
    "MLB — Mariners":     "#0C2C56",
    "MLB — Cardinals":    "#C41E3A",
    "MLB — Rays":         "#092C5C",
    "MLB — Rangers":      "#003278",
    "MLB — Blue Jays":    "#134A8E",
    "MLB — Nationals":    "#AB0003",

    # ── Magic: The Gathering (mana colors) ──
    "MTG — White": "#E8E0C0",
    "MTG — Blue":  "#0E68AB",
    "MTG — Black": "#6D6E70",
    "MTG — Red":   "#D3202A",
    "MTG — Green": "#00733E",

    # ── Pokémon (a few popular types) ──
    "Pokémon — Fire":      "#F08030",
    "Pokémon — Water":     "#6890F0",
    "Pokémon — Grass":     "#78C850",
    "Pokémon — Electric":  "#F8D030",
    "Pokémon — Psychic":   "#F85888",
}


def extract_accent_from_image(path: str) -> Optional[str]:
    """
    Pull a vivid accent color from a card image via k-means clustering.

    Returns a hex string, or None on failure. Picks the cluster that best
    balances vividness (saturation × brightness) with how much of the image
    it covers — i.e. a bold, representative color rather than a muted one.
    """
    try:
        import cv2
        import numpy as np

        img = cv2.imread(path)
        if img is None:
            return None
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Downscale for speed
        h, w = img.shape[:2]
        scale = 200 / max(h, w)
        if scale < 1:
            img = cv2.resize(img, (int(w * scale), int(h * scale)),
                             interpolation=cv2.INTER_AREA)

        pixels = img.reshape(-1, 3).astype(np.float32)
        K = 5
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, labels, centers = cv2.kmeans(
            pixels, K, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
        centers = centers.astype(np.uint8)
        counts = np.bincount(labels.flatten(), minlength=K).astype(np.float32)
        counts /= counts.sum()

        best_hex, best_score = None, -1.0
        for i, (r, g, b) in enumerate(centers):
            hsv = cv2.cvtColor(np.uint8([[[r, g, b]]]), cv2.COLOR_RGB2HSV)[0][0]
            sat, val = hsv[1] / 255.0, hsv[2] / 255.0
            # Skip near-white / near-black (poor accents on a dark UI)
            if val < 0.20 or val > 0.95 and sat < 0.15:
                continue
            score = (sat * 0.7 + val * 0.3) * (0.5 + counts[i])
            if score > best_score:
                best_score = score
                best_hex = f"#{r:02x}{g:02x}{b:02x}"

        return best_hex
    except Exception as exc:
        logger.warning("Accent extraction failed for %s: %s", path, exc)
        return None

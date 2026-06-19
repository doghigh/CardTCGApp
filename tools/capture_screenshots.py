"""
Generate clean, trademark-free Microsoft Store listing screenshots.

Why this exists
---------------
The Store rejected the prior screenshots under policy 10.1.1.3 (Inaccurate
Representation) because the listing imagery contained third-party trademarks and
real card/player names ("Magic: The Gathering", "Topps", real player names) —
i.e. imagery from products not published by us.

This script renders the real app UI headlessly (Qt offscreen) against a seeded
*fictional* demo collection containing zero third-party IP, and saves uniform
1920x1080 PNGs to screenshots/sc1..sc4.png.

Safety: APPDATA is redirected to a throwaway temp dir BEFORE any app module is
imported, so the user's real %APPDATA%/Lorebox/cards.db, config, and prefs are
never read or written.

Run:  python tools/capture_screenshots.py
"""

import os
import sys
import sqlite3
import tempfile
from datetime import date, timedelta
from pathlib import Path

# --- 1) Sandbox the app's data dir + suppress first-run dialogs --------------
# Must happen before importing core.config / ui.* (they read APPDATA at import).
DEMO_APPDATA = Path(tempfile.mkdtemp(prefix="lorebox_shots_"))
os.environ["APPDATA"] = str(DEMO_APPDATA)
# A non-empty key makes _prompt_for_keys_if_needed() skip its blocking dialog.
os.environ.setdefault("ANTHROPIC_API_KEY", "demo-screenshot-key")
# NOTE: do NOT use QT_QPA_PLATFORM=offscreen here — on Windows the offscreen
# platform plugin fails to load the system font database, so every glyph
# renders as a tofu box. We use the native platform (real fonts) plus
# WA_DontShowOnScreen below, which lays out + renders the window for grab()
# without ever flashing it on screen.

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SHOTS = ROOT / "screenshots"
SHOTS.mkdir(exist_ok=True)

W, H = 1920, 1080

# --- 2) Fictional, trademark-free demo collection ----------------------------
# Invented card names, invented sets, invented players. "Fantasy TCG" /
# "Sci-Fi TCG" are generic descriptors (not brands). Baseball/Basketball are
# generic sports, not manufacturers.
DEMO_CARDS = [
    # Fantasy TCG — set "Mythic Origins"
    dict(name="Aetherwing Drake", set_name="Mythic Origins", card_number="142/240",
         rarity="Mythic Rare", game="Fantasy TCG", year=2025, foil=1,
         condition_grade="Gem Mint", condition_score=96.0,
         estimated_value=48.00, purchase_price=22.00),
    dict(name="Thornroot Sentinel", set_name="Mythic Origins", card_number="088/240",
         rarity="Rare", game="Fantasy TCG", year=2025,
         condition_grade="Near Mint", condition_score=82.0,
         estimated_value=9.50, purchase_price=4.00),
    dict(name="Emberveil Sprite", set_name="Mythic Origins", card_number="015/240",
         rarity="Common", game="Fantasy TCG", year=2025,
         condition_grade="Excellent", condition_score=70.0,
         estimated_value=0.75, purchase_price=0.25),
    # Sci-Fi TCG — set "Nova Frontier"
    dict(name="Orbital Dreadnought", set_name="Nova Frontier", card_number="201/210",
         rarity="Ultra Rare", game="Sci-Fi TCG", year=2024, foil=1,
         condition_grade="Mint", condition_score=90.0,
         estimated_value=33.00, purchase_price=18.00),
    dict(name="Quantum Courier", set_name="Nova Frontier", card_number="134/210",
         rarity="Uncommon", game="Sci-Fi TCG", year=2024,
         condition_grade="Near Mint", condition_score=83.0,
         estimated_value=3.25, purchase_price=1.50),
    dict(name="Nebula Scout", set_name="Nova Frontier", card_number="077/210",
         rarity="Common", game="Sci-Fi TCG", year=2024,
         condition_grade="Very Good", condition_score=58.0,
         estimated_value=0.40, purchase_price=0.10),
    # Baseball — set "Diamond Classic"
    dict(name="Cole Brackett", set_name="Diamond Classic", card_number="351",
         rarity=None, game="Baseball", year=2023,
         condition_grade="Near Mint", condition_score=81.0,
         estimated_value=12.00, purchase_price=6.00),
    dict(name="Marcus Vance", set_name="Diamond Classic", card_number="486",
         rarity=None, game="Baseball", year=2023,
         condition_grade="Excellent", condition_score=72.0,
         estimated_value=5.50, purchase_price=2.00),
    # Basketball — set "Hardcourt Legends"
    dict(name="Davon Pierce", set_name="Hardcourt Legends", card_number="23",
         rarity=None, game="Basketball", year=2022,
         condition_grade="Near Mint", condition_score=84.0,
         estimated_value=18.00, purchase_price=9.00),
    dict(name="Eli Townsend", set_name="Hardcourt Legends", card_number="07",
         rarity=None, game="Basketball", year=2022, foil=1,
         condition_grade="Gem Mint", condition_score=95.0,
         estimated_value=27.50, purchase_price=14.00),
]


def seed(db_path: Path) -> None:
    """Insert demo cards and a rising 14-day value-history line."""
    from core.database import Database
    db = Database(db_path)
    for c in DEMO_CARDS:
        db.add_card(c)

    total = sum(c["estimated_value"] for c in DEMO_CARDS)
    cost = sum(c["purchase_price"] for c in DEMO_CARDS)
    n = len(DEMO_CARDS)
    # 13 past daily snapshots rising toward today's real total (refresh adds today).
    conn = sqlite3.connect(str(db_path))
    try:
        for i in range(13, 0, -1):
            d = (date.today() - timedelta(days=i)).isoformat()
            frac = (14 - i) / 14.0
            v = round(total * (0.78 + 0.22 * frac), 2)   # ~78% -> ~100% of total
            conn.execute(
                "INSERT OR REPLACE INTO value_history "
                "(snapshot_date, total_value, total_cost, total_cards, total_quantity) "
                "VALUES (?,?,?,?,?)",
                (d, v, round(cost * (0.85 + 0.15 * frac), 2), n, n),
            )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from utils.theme import apply_dark_theme
    from core.config import APP_DIR, set_pref

    app = QApplication(sys.argv)
    apply_dark_theme(app)

    # Skip the one-time welcome dialog (writes to the sandboxed prefs.json).
    set_pref("welcome_ack", date.today().isoformat())

    seed(APP_DIR / "cards.db")

    from ui.main_window import MainWindow
    win = MainWindow()
    # Lay out + render for grab() without ever appearing on screen.
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(W, H)

    # Populate the Scan & Add form so it looks in-use — fictional card, no brands.
    st = win.scan_tab
    st.name_edit.setText("Aetherwing Drake")
    st.set_edit.setText("Mythic Origins")
    st.number_edit.setText("142/240")
    st.rarity_edit.setText("Mythic Rare")
    st.game_combo.setCurrentText("Fantasy TCG")   # editable combo; avoids the MTG default
    st.year_spin.setValue(2025)
    st.purchase_spin.setValue(22.00)
    st.lang_edit.setText("English")
    # Neutralise any real scanner brand the live machine's TWAIN reported
    # (e.g. "EPSON DS-575W") — generic label keeps the listing brand-free.
    st.source_combo.clear()
    st.source_combo.addItem("Flatbed Scanner (TWAIN)")

    # Make sure every tab has fresh data, then lay out.
    for t in (win.dashboard_tab, win.collection_tab, win.reports_tab):
        if hasattr(t, "refresh"):
            t.refresh()
    win.show()
    app.processEvents()

    targets = [(0, "sc1"), (1, "sc2"), (2, "sc3"), (3, "sc4")]  # Dashboard, Scan, Batch, Collection
    for idx, name in targets:
        win.tabs.setCurrentIndex(idx)
        if win.tabs.widget(idx) is win.dashboard_tab:
            win.dashboard_tab.refresh()
        app.processEvents()
        app.processEvents()
        pix = win.grab()
        # Display DPI scaling can make the grab larger than logical size
        # (e.g. 2400x1350 at 125%). Normalise every shot to a uniform,
        # standard 1920x1080 — source is 16:9 so there's no distortion.
        if (pix.width(), pix.height()) != (W, H):
            pix = pix.scaled(W, H, Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        out = SHOTS / f"{name}.png"
        pix.save(str(out))
        print(f"{name}: {pix.width()}x{pix.height()} -> {out}")

    print(f"\nSandbox data dir (safe to delete): {DEMO_APPDATA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Help Center content. Each entry is a topic title → Markdown body, rendered
in-app via QTextBrowser.setMarkdown() (no external dependency, works offline).

Kept as a Python module (not loose .md files) so it packages cleanly into
the MSIX/PyInstaller build with no path lookups.
"""

HELP_TOPICS = {
    "Welcome": """
# Welcome to Lorebox

Catalog, grade, and value your trading card collection — sports cards, Magic,
Pokémon, and more.

**The basics**
1. Add an **Anthropic API key** in *Settings* so the app can identify cards.
2. **Scan** cards, **load** image files, or **batch import** a folder.
3. Each card is identified, graded for condition, and priced automatically.
4. Browse everything in **Collection** and see an overview on the **Dashboard**.

Use the list on the left to read about any feature. Press **F1** anytime to
open this Help Center.
""",

    "Setting Up API Keys": """
# Setting Up API Keys

The app uses your own API keys, stored **encrypted** on your computer. You only
pay your providers for what you use.

## Anthropic (required for identification)
1. Go to **console.anthropic.com → Settings → API Keys**.
2. Create a key and copy it.
3. In the app: **File → Settings** → paste it into *Anthropic API Key* → **Test**.

Cost is about **half a cent per card** scanned.

## eBay (optional, for valuation)
1. Go to **developer.ebay.com → My Account → Application Keys**.
2. Use your **Production** App ID and Cert ID (not Sandbox).
3. Paste both into *Settings* and click **Test**.

eBay lookups are free. Without eBay keys, Magic cards are still valued via
Scryfall; other cards will show no estimate until you add eBay keys.
""",

    "Scanning Cards": """
# Scanning Cards

1. On the **Scan & Add** tab, choose your scanner and DPI (400 is a good default).
2. Tick **Enable Duplex** to capture front and back in one pass.
3. Click **📷 Scan Card**. The whole feeder is scanned in one run.
4. After scanning you can **Scan More Cards** or **End Scanning**.

- **One card** loads straight into the viewer to review and save.
- **Multiple cards** open the Batch Review screen — all are processed in
  parallel, then you review and save them together.

**Rotation:** under each image are **↺ 90° · 180° · ↻ 90° · 📐 Straighten**
buttons. Straighten auto-corrects small tilt. Cards are auto-straightened on
scan anyway.
""",

    "Loading Image Files": """
# Loading Image Files

No scanner? Use **📂 Load Front** and **📂 Load Back** on the Scan & Add tab to
pick image files (PNG/JPG/etc.). The card is identified and graded just like a
scan, then you can save it.
""",

    "Batch Import": """
# Batch Import

Open the **Batch Import** tab to add many cards at once.

## Image Folder
Point it at a folder of card images **or PDFs**. Choose how files pair into cards:

- **One image = one card** — single-sided scans.
- **Sequential (1=front, 2=back)** — duplex scans saved in order.
- **By filename** — matches `name_front` with `name_back` (also `_f`/`_b`, `-1`/`-2`).
- **By orientation** — portrait pages are fronts, landscape pages are backs
  (e.g. vintage Topps, whose backs print sideways). Each back pairs with its front.

Tick **Auto-fetch online values** to price them during import.

## CSV Import
Import an existing spreadsheet. Click **Download Template** for the format, fill
it in, then **Select CSV File** and map the columns.
""",

    "Watch Folder (Auto-Import)": """
# Watch Folder — Auto-Import

Have the app import scans automatically on a schedule.

1. Batch Import tab → **🕒 Auto-Import Watch Folder** → tick **Enable**.
2. Choose the folder you'll drop scans into.
3. Pick a schedule — **Daily at a set time** or **Every N minutes**.
4. Choose the front/back pairing mode and whether to auto-value.

Dropped files are imported on schedule, then moved into an `imported/` subfolder
so they're never processed twice. **▶ Run Now** triggers it immediately.

*The app must be running for the watch to fire.*
""",

    "The Collection": """
# The Collection

Your full library, with a search box and sortable columns (click any header).

**Toolbar actions** (select rows first):
- **💰 Re-value Selected** — refresh market prices.
- **🔍 Re-identify Selected** — re-read name/set from the saved scans (handy for
  cards that were misread). Uses the vision API.
- **🔁 Merge Duplicates** — combine duplicate rows into one with summed quantity.
- **🗑 Delete Selected** — remove cards.
- **📤 Export CSV** — export your whole collection.

**Double-click a card** to open its detail view, where you can edit any field and
rotate/straighten the images. Duplicate cards merge automatically as you add them.
""",

    "Card Identification": """
# Card Identification

The app sends the card image to Claude (Anthropic) and reads the name, set, card
number, year, and game type.

- For **vintage Magic** cards it ignores the "Summon …" type line and reads the
  title at the top.
- If a card is misidentified, either **double-click → edit** the fields, or select
  it and use **🔍 Re-identify Selected** to try again from the scan.

Good, in-focus scans identify best. Very worn or blurry cards may need a manual fix.
""",

    "Grading & Condition": """
# Grading & Condition

Each card gets a condition **grade** and a **0–100 score** from an automated
visual inspection that looks at corners, edges, surface, and centering.

Grades range from **Gem Mint** down to **Poor**. The grade adjusts the estimated
value (a Near Mint card is worth more than a Played one). You can override the
grade anytime in a card's detail view.

> **Automated estimate — not guaranteed.** The grade is a software guess from a
> single image and is **not** a professional grade. It does **not** predict or
> guarantee what PSA, BGS, SGC, or any grading company would assign, and
> shouldn't be relied on for buying, selling, or insurance decisions. For an
> authoritative grade, use a professional grading service.
""",

    "Valuation": """
# Valuation

Lorebox shows an **estimated** market value drawn from public data:

- **Magic: The Gathering** → **Scryfall** (official, free USD pricing).
- **Other cards** → **eBay** current listings (if you've added eBay keys).

The figure is adjusted for the card's condition grade. Use **Re-value Selected**
in the Collection to refresh anytime. A value of **$0.00** usually means no
market data was found (a token, an obscure card, or a misidentified name).

> **Estimates only — not guaranteed.** Card prices change constantly and vary by
> grade, seller, and marketplace. The value shown is an approximate guide based
> on available listings, **not** a guaranteed sale price, a professional
> appraisal, or financial/investment advice. Always confirm against live
> listings before buying or selling.
""",

    "Dashboard": """
# Dashboard

Your collection at a glance:

- **KPI cards** — unique cards, total quantity, estimated value, cost, net P&L,
  average condition.
- **Value over time** — a line chart that fills in as daily snapshots accumulate.
- **Value by Game** and **Cards by Grade** — relative bars.
- **Set Completion** — progress for recognized sets (e.g. 1986 Topps = 792).
- **Most Valuable** and **Recently Added** tables.

**Tip:** click a game or set bar to jump to a filtered Collection; double-click a
card in the tables to open it.
""",

    "Themes & Appearance": """
# Themes & Appearance

**File → Settings → Appearance** lets you recolor the app:

- **Presets** — 30 MLB teams, Magic mana colors, and Pokémon types.
- **Custom…** — pick any color.
- **From card…** — pull a color straight from one of your card images.

Changes apply instantly and are remembered between sessions.
""",

    "Accessibility": """
# Accessibility

Under **File → Settings → Appearance**:

- **Text size** — Small / Normal / Large / Extra Large scales the whole interface.
- **High-contrast mode** — black/white with a bright focus outline for low vision.

Everything is **keyboard navigable** — use **Tab / Shift+Tab** to move between
controls, **Space/Enter** to activate, and the focus outline shows where you are.
Icon-only buttons and image previews are labeled for screen readers (Narrator).
""",

    "Keyboard Shortcuts": """
# Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **Ctrl+1 … Ctrl+5** | Switch tabs (Dashboard → Reports) |
| **Ctrl+N** | New card (Scan & Add) |
| **Ctrl+S** | Save the current card |
| **Ctrl+F** | Focus the Collection search box |
| **Ctrl+,** | Open Settings |
| **F5** | Refresh all views |
| **F1** | Open this Help Center |
| **Ctrl+Q** | Quit |
""",

    "Privacy & Data": """
# Privacy & Data

- Your collection, scans, and settings are stored **only on your computer**
  (under `%APPDATA%\\Lorebox` — [📂 open it](lorebox:data)).
- Card images go to **Anthropic** for identification and card names go to
  **eBay and Scryfall** for pricing — using **your** API keys.
- API keys are stored **encrypted**. There is **no analytics or tracking**.
- The full policy is in **Help menu → Privacy Policy**.
""",

    "Troubleshooting & FAQ": """
# Troubleshooting & FAQ

| Problem | What to do |
|---------|------------|
| **Cards aren't being identified** | Add a valid Anthropic API key in *Settings → API Keys* and click **Test**. |
| **Value shows $0.00** | No market data was found. Confirm the card's name/set is correct (edit or re-identify it). Tokens and very obscure cards often have no listed price. |
| **Everything graded Poor / wrong grade** | Grading is an automated estimate — open the card's detail view and adjust the grade manually. |
| **Front and back imported as two cards** | In Batch Import, pick the right **pairing mode** (Sequential, By filename, or By orientation) for how your files are arranged. |
| **A scan looks grainy** | Make sure your scanner isn't saving compressed JPEGs; Lorebox captures uncompressed where possible. |
| **eBay valuation isn't working** | Use your **Production** eBay App ID + Cert ID (not Sandbox), and click **Test** in Settings. |
| **Where are the logs?** | [📂 Open the logs folder](lorebox:logs) — attach `app.log` if you report an issue. |
| **Where is my data stored?** | [📂 Open your data folder](lorebox:data) — everything is local (collection, scans, settings). |
""",
}

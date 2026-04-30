# CardTCGApp

A Windows desktop application for managing your trading card collection. Scan cards directly from a TWAIN-compatible scanner, automatically grade condition with computer vision, pull live market values from multiple sources, and generate monthly portfolio reports.

Built with Python + PyQt6. Runs as a native Windows app or as a standalone `.exe`.

---

## Features

- **TWAIN scanner integration** — scan card fronts and backs directly into the app at configurable DPI
- **Automatic card identification** — OCR (Tesseract) reads the card name and number from the scan
- **Computer-vision condition grading** — OpenCV inspects corners, edges, surface, and centering to assign a grade from Gem Mint to Poor with a 0–100 score and a list of detected defects
- **Multi-source valuation** — fetches prices in parallel from TCGPlayer, eBay sold listings, and PriceCharting, then computes a condition-adjusted estimate
- **Local SQLite database** — your collection lives in `%APPDATA%\TradingCardManager\cards.db`; no cloud, no account, no telemetry
- **Searchable collection view** — color-coded condition scores, totals, net profit, CSV export
- **Monthly PDF reports** — collection summary, the month's additions, top 25 cards by value, condition distribution
- **Graceful degradation** — works without a scanner (load images from disk), without Tesseract (manual entry), and without internet (skip valuation)

---

## Requirements

- Windows 10 or 11
- Python 3.10 or later ([python.org](https://www.python.org/downloads/) — make sure to check **Add Python to PATH** during install)
- A TWAIN-compatible scanner (optional — you can also load images from disk)
- [Tesseract OCR for Windows](https://github.com/UB-Mannheim/tesseract/wiki) (optional, enables auto-identification)

---

## Quick start

1. Clone the repo:
   ```
   git clone https://github.com/doghigh/CardTCGApp.git
   cd CardTCGApp
   ```
2. Double-click `run.bat`. On first launch it creates a virtual environment, installs dependencies, and starts the app. Subsequent launches start instantly.

That's it.

---

## Build a standalone .exe

If you want to ship the app to a machine without Python:

1. Double-click `build_exe.bat`
2. Wait for PyInstaller to finish
3. Grab `dist\TradingCardManager.exe` — single file, no dependencies needed on the target machine

---

## Usage

### Scan tab
Pick your TWAIN source, set DPI (300 is a good default), and scan the front and back of a card. The app will:
1. Run OCR to auto-fill the name and card number
2. Run the inspection pipeline and show grade, score, and detected defects
3. Let you click **Fetch Value** to query the price sources

Fill in any missing fields (set, rarity, game, etc.), then **Save to Collection**.

### Collection tab
- Search by name, set, or game
- Double-click a row to see both scans plus full details
- Sort by any column; condition score cells are color-coded (green = mint, red = damaged)
- Re-value selected cards to refresh prices
- Export the whole collection to CSV

### Reports tab
- Pick a year and month, click **Generate Report**
- A PDF lands in `%APPDATA%\TradingCardManager\reports\` and is listed in the panel
- Double-click any past report to open it

---

## Where your data lives

```
%APPDATA%\TradingCardManager\
    cards.db          SQLite database (cards, valuations, reports)
    scans\            PNG scans of every card front/back
    reports\          Generated PDF reports
```

To back up your collection, copy that whole folder. To start fresh, delete it.

---

## Tech stack

| Component | Library |
|---|---|
| UI | PyQt6 (Fusion dark theme) |
| Database | SQLite (stdlib `sqlite3`) |
| Scanner | pytwain |
| Image processing | OpenCV, NumPy, Pillow |
| OCR | pytesseract |
| Web scraping | requests, BeautifulSoup |
| PDF reports | reportlab |
| Packaging | PyInstaller |

---

## Known limitations

- **Price scrapers may break.** TCGPlayer, eBay, and PriceCharting periodically change their HTML. The scrapers use generic CSS-class regex patterns; if a source stops returning prices, the selectors in `CardValuator` need a refresh.
- **OCR accuracy depends on Tesseract.** If `pytesseract` can't find Tesseract, point it at your install by editing the top of `main.py`:
  ```python
  pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
  ```
- **TWAIN driver quality varies by scanner.** If scanning fails, your scanner's TWAIN driver may need to be reinstalled or updated from the manufacturer.
- **Condition grading is heuristic.** It catches obvious damage (corner whitening, edge wear, creases, off-center cuts) but is not a substitute for professional grading by PSA/BGS/CGC for high-value cards.

---

## Project structure

```
CardTCGApp/
├── main.py              # Full application (~1600 lines)
├── requirements.txt     # Python dependencies
├── run.bat              # First-run setup + launcher
├── build_exe.bat        # PyInstaller build script
├── .gitignore
└── README.md
```

---

## License

MIT. Do whatever you want with it.

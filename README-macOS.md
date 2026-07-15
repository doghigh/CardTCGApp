# Running Lorebox on macOS

Lorebox is a Python / PyQt6 desktop app and runs on macOS from source.
Everything works **except direct flatbed scanning** (TWAIN is Windows-only) —
on macOS you import from image files and PDFs instead.

## Requirements

- Python 3.10+
- Anthropic + eBay developer API keys (free to create) — for card identification
  and market values. Anthropic charges about **$0.006 per card** identified.
- Tesseract OCR — **optional**, only used as a fallback when no Anthropic key is set.

## Install

### 1. Homebrew packages

If you don't have [Homebrew](https://brew.sh), install it first, then:

    brew install python tesseract

### 2. Get the code and launch

    git clone https://github.com/doghigh/CardTCGApp.git lorebox
    cd lorebox            # this directory contains main.py and run.sh
    chmod +x run.sh
    ./run.sh

`run.sh` creates a virtual environment, installs the dependencies, and starts
the app. (`pytwain` is skipped automatically off Windows.)

Prefer to do it by hand:

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    python main.py

## API keys

Enter them in the in-app **Settings** dialog, or create a `.env` file next to
`main.py`:

    ANTHROPIC_API_KEY=sk-ant-...
    EBAY_APP_ID=...
    EBAY_CERT_ID=...

Create the keys (both free) at https://platform.claude.com and
https://developer.ebay.com

## Where your data lives

By default everything (database, card scans, config, logs) goes in:

    ~/Lorebox/

To keep it somewhere else, set `LOREBOX_DATA_DIR` in `.env`:

    LOREBOX_DATA_DIR=/Users/you/lorebox-data

## What works / what doesn't

- ✅ File & PDF **Batch Import**, Claude-vision identification and condition
  grading, market valuation, collection, reports, dashboard, and LAN sync from
  the companion phone app.
- ❌ **Direct flatbed (TWAIN) scanning** — Windows-only. On macOS, scan with
  Image Capture / Preview (or any tool that saves images or PDFs), then use
  **Batch Import**.
- OCR fallback (optional): Homebrew installs Tesseract at `/opt/homebrew/bin`
  (Apple Silicon) or `/usr/local/bin` (Intel). If OCR isn't auto-detected,
  make sure `tesseract` is on your `PATH` or set `TESSERACT_CMD` in `.env`.
  This only matters when you have no Anthropic key (primary identification is
  the Claude vision API).

## Troubleshooting

- **"Python was not installed as a framework" / Qt display errors:** use the
  Homebrew `python` (not the system one) and run inside the venv created by
  `run.sh`.
- **Starts but can't identify cards:** set your Anthropic API key (Settings or
  `.env`).

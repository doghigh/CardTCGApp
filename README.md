            # Lorebox

            A **privacy-first**, Windows desktop application for managing your physical 
            trading card collection (TCG, Sports Cards, etc.).

            You will need developer accounts with Anthropic and Ebay. 
            These are free to enroll. Anthropic charges $0.006 per card submission 
            or 6 cents for 10 cards. 
            
https://platform.claude.com/login?returnTo=%2F%3F

https://developer.ebay.com/

            Scan cards with a TWAIN-compatible scanner, 
            automatically identify them with OCR, 
            grade condition using computer vision, 
            fetch live market values, 
            and generate beautiful monthly PDF reports — all **100% locally**.

            ---

            ## ✨ Features

            - **TWAIN Scanner Integration** — Direct scanning of card fronts and backs
            - **Auto Card Identification** — Claude vision API (Tesseract OCR fallback)
            - **AI Condition Grading** — OpenCV analyzes corners, edges, surface, centering, and defects
            - **Live Market Values** — Scryfall (Magic) and the eBay Browse API — official APIs only
            - **Local SQLite Database** — Your collection stays private (no cloud, no account)
            - **Batch Import** — Import from image folders or CSV with smart column mapping
            - **Continuous Scan Mode** — High-volume scanning with auto-save
            - **Monthly PDF Reports** — Professional reports with charts and summaries
            - **Full Keyboard Accessibility** — Ctrl+1–4, Ctrl+N, F1 help, etc.
            - **Single-file .exe** — Easy distribution

            ---

## 📸 Screenshots

*(Add screenshots here when you have them)*

---

## 🚀 Quick Start

1. Install from Microsoft App Store https://apps.microsoft.com/detail/9N94V4458M3V
2. Double-click `LoreBox` Icon (first run will assist with links to create dev accounts)
3. Create API Keys for each, copy and paste into the settings
4. Start scanning!

### Requirements

- **Windows 10 or 11**
- Python 3.10+ (included via venv)
- TWAIN-compatible scanner (optional)
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (optional OCR fallback)
- Developer Accounts and API keys from Anthropic and Ebay (Anthropic allows for Card Identification, it has identified cards from Dessert Storm, Star Wars, MTG, Sports, Last Air Bender, etc)

### Running on Linux or macOS

Lorebox also runs from source on Linux and macOS (everything except direct
flatbed/TWAIN scanning — use file/PDF import there). See
[README-Linux.md](README-Linux.md) and [README-macOS.md](README-macOS.md).
--

## 📄 License

Lorebox is open source under the **GNU Affero General Public License v3.0**
(AGPL-3.0) — see [LICENSE](LICENSE).

Copyright (C) 2026 Jesse Catlow. The author retains copyright and may also offer
the software under separate commercial terms.

Lorebox is an independent application and is not affiliated with or endorsed by
Anthropic, eBay, Scryfall, The Topps Company, Wizards of the Coast, or any
trading card manufacturer. Product names and trademarks are the property of
their respective owners.

---

## 📁 Project Structure

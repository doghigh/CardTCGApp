# Trading Card Manager

A **privacy-first**, Windows desktop application for managing your physical trading card collection (TCG, Sports Cards, etc.).

Scan cards with a TWAIN-compatible scanner, automatically identify them with OCR, grade condition using computer vision, fetch live market values, and generate beautiful monthly PDF reports — all **100% locally**.

---

## ✨ Features

- **TWAIN Scanner Integration** — Direct scanning of card fronts and backs
- **Auto Card Identification** — Tesseract OCR with smart parsing
- **AI Condition Grading** — OpenCV analyzes corners, edges, surface, centering, and defects
- **Live Market Values** — Parallel lookups from TCGPlayer, eBay Sold, and PriceCharting
- **Local SQLite Database** — Your collection stays private (no cloud, no account)
- **Batch Import** — Import from image folders or CSV with smart column mapping
- **Continuous Scan Mode** — High-volume scanning with auto-save
- **Monthly PDF Reports** — Professional reports with charts and summaries
- **Windows Hello + TOTP 2FA** — Modern authentication (optional)
- **Full Keyboard Accessibility** — Ctrl+1–4, Ctrl+N, F1 help, etc.
- **Single-file .exe** — Easy distribution

---

## 📸 Screenshots

*(Add screenshots here when you have them)*

---

## 🚀 Quick Start

1. **Download or clone** the project
2. Double-click `run.bat` (first run will install everything)
3. On first launch, set a master password (optional but recommended)
4. Start scanning!

### Requirements

- **Windows 10 or 11**
- Python 3.10+ (included via venv)
- TWAIN-compatible scanner (optional)
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (recommended)

---

## 📁 Project Structure
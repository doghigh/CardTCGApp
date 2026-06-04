# Trading Card Manager — TODO

**Repository:** https://github.com/doghigh/CardTCGApp  
**Last updated:** 2026-06-04  
**Branch:** main

---

## ✅ Completed This Session

### Card Identification
- [x] Replace fragile Tesseract OCR pipeline with Claude vision API (claude-haiku)
- [x] Accurate name, set, card #, year, game type from a single API call
- [x] Automatic OCR fallback when `ANTHROPIC_API_KEY` is not set
- [x] Multi-strategy OCR preprocessing (adaptive, Otsu, inverted)
- [x] Header-region extraction for white-on-colour text (sports card names)
- [x] Game type detection (Baseball, Basketball, MTG, Pokémon, etc.)
- [x] Year extraction from card text

### Scanning
- [x] Single **Scan Card** button — scans entire feeder in one run
- [x] After scan: **Scan More Cards / End Scanning** dialog to accumulate pages
- [x] Multiple cards auto-split into per-card chunks (duplex-aware)
- [x] Per-card review queue: **Save & Next / Skip / Stop**
- [x] Single card skips queue and loads straight into the viewer
- [x] Batch Import uses Claude vision for identification

### UI / Theme
- [x] Modern dark theme (VS Code / Linear style — indigo accent, deep backgrounds)
- [x] Fixed Fusion palette Mid/Dark/Shadow to eliminate cyan borders
- [x] Fixed `_is_high_contrast()` — was routing dark-mode users to old stylesheet
- [x] Group box titles rendering correctly on the border line
- [x] Right panel scrollable — Save Card pinned at bottom
- [x] Tab bar with indigo underline indicator
- [x] Primary button style (Scan Card, Save Card, Generate Report, Start Import)
- [x] Batch Import polished — group boxes, proper button widths, filename label
- [x] Reports tab — stats bar (unique/total/value/cost/net P&L), group boxes
- [x] All hardcoded old colours removed from collection_tab, dialogs, batch_tab
- [x] App opens maximized

### Code Quality
- [x] `.gitignore` updated — `__pycache__`, `.pyc`, `.env`, `.claude/settings.local.json`
- [x] All `.pyc` files untracked and removed from repo
- [x] `.env` file loading at startup (zero dependencies)
- [x] `.env.example` with documented keys
- [x] `anthropic>=0.40.0` added to `requirements.txt`
- [x] 6 Pylance type errors fixed in `scan_tab.py`
- [x] Continuous Scan button removed (simplified to one Scan Card button)

### Bugs Fixed (from previous todo)
- [x] BUG-A: `cv2` not imported in `batch_tab.py`
- [x] BUG-B: `ImageBatchWorker` missing `db` parameter
- [x] BUG-C: `dialog.get_mapping()` → `dialog.mapping`
- [x] BUG-D: Defects panel never populated in `_inspect()`
- [x] BUG-E: Dead bare `QThread()` object
- [x] BUG-G: Duplicate tab emoji
- [x] P-7: Dead `ui/collections.py` removed

---

## 🔴 Active Issues

### Grading — Poor (0.0/100) on all cards
- Every scanned card is graded "Poor 0.0/100" regardless of condition
- The `CardInspector` defect detection is likely over-triggering (corner whitening on all 4 corners + edge whitening = near-zero score)
- **Fix:** Review `core/inspector.py` thresholds — likely needs tuning for scan noise vs. real defects

### Collection row 1 — OCR garbage entry
- Card ID 80: `"a so ee ee — - a a ."` — created before Claude vision was active
- **Fix:** Delete manually from the collection tab, or add a bulk-delete option

---

## 🟡 Logic / UX

| # | Issue | Location |
|---|-------|----------|
| UX-1 | Grade shown as "Poor 0.0" in red on every card — needs inspector calibration | `core/inspector.py` |
| UX-2 | Estimated value always $0.00 — valuator not wired to auto-fetch on save | `ui/scan_tab.py`, `core/valuator.py` |
| UX-3 | Collection tab: clicking a row should open card detail / edit dialog | `ui/collection_tab.py` |
| UX-4 | No duplicate detection — scanning the same card twice adds two rows | `core/database.py` |
| UX-5 | `update_card` defects branch unreachable — `'defects'` not in allowed set | `core/database.py:112` |
| UX-6 | Re-value Selected runs on main thread — freezes UI for large selections | `ui/collection_tab.py` |
| UX-7 | Reports tab: stats bar emojis rendering as icon placeholders on some systems | `ui/reports_tab.py` |

---

## 🟠 Security

| # | Issue | Status |
|---|-------|--------|
| SEC-1 | Password storage migration — old `.auth.key` files (raw bytes) lock users out after SHA256 fix | Needs migration check |
| SEC-2 | Bare `except:` handlers swallow errors silently | Multiple files |
| SEC-3 | No input validation before database INSERT | `core/database.py:73` |
| SEC-4 | No rate limiting / retry in web scrapers — risks IP ban | `core/valuator.py` |
| SEC-5 | TOTP secret stored in plaintext on disk | `core/auth.py` |

---

## 🔵 Low Priority / Polish

| # | Issue | Location |
|---|-------|----------|
| P-1 | `print()` used everywhere — no logging framework | Multiple |
| P-2 | `requirements.txt` has unpinned versions (`>=`) | `requirements.txt` |
| P-3 | No unit tests for auth, database, or valuation | — |
| P-4 | Windows Hello auth has no guaranteed password fallback | `core/auth.py` |
| P-5 | `base64` imported but unused | `core/auth.py:8` |
| P-6 | File comment in `reports_generator.py` says wrong filename | Line 1 |
| P-7 | Scan tab toolbar has no visual separator between scanner controls and action buttons | `ui/scan_tab.py` |
| P-8 | `QInputDialog` imported mid-file instead of at top | `core/auth.py:99` |

---

## 📋 Next Priority Order

### High — affects daily use
- [ ] Calibrate `CardInspector` thresholds so cards don't all grade as Poor (UX-1)
- [ ] Wire estimated value auto-fetch on save (UX-2)
- [ ] Add card detail / edit dialog on collection row click (UX-3)

### Medium
- [ ] Add duplicate detection on scan/save (UX-4)
- [ ] Fix `update_card` defects branch (UX-5)
- [ ] Move re-value to background thread (UX-6)
- [ ] Password migration check for old `.auth.key` format (SEC-1)

### Before Release
- [ ] Replace bare exception handlers (SEC-2)
- [ ] Add input validation on database INSERT (SEC-3)
- [ ] Add rate limiting to web scrapers (SEC-4)
- [ ] Add unit tests for core modules (P-3)

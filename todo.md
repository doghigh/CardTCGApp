# Trading Card Manager — TODO

**Repository:** https://github.com/doghigh/CardTCGApp
**Last updated:** 2026-06-08
**Branch:** main
**Goal:** Ship to the Microsoft Store

---

## ✅ Completed (recent sessions)

### Dashboard & Personalization (this session)
- [x] Dashboard home tab — KPIs, value-by-game & cards-by-grade bars, top/recent tables
- [x] Value-over-time line chart (daily snapshots in value_history table)
- [x] Clickable game/set bars → filtered Collection; double-click card → detail
- [x] Set-completion tracking (known set sizes, e.g. 1986 Topps = 792)
- [x] Custom accent themes — 40 presets (MLB teams, MTG, Pokémon), custom picker,
      and extract-colour-from-card-image
- [x] Accessibility — adjustable text size, high-contrast mode, visible keyboard
      focus, screen-reader labels on icon-only controls

### Valuation
- [x] eBay Browse API (OAuth client-credentials) for sold/active prices
- [x] Scryfall integration for Magic cards (free, official, reliable)
- [x] PriceCharting fallback with throttle + 429 backoff (no IP bans)
- [x] Scryfall search fallback rescues cards with bad set fields
- [x] eBay category fix — non-sport cards (Star Wars etc.) no longer forced into CCG
- [x] Estimated value auto-fetched on save (scan + batch)
- [x] Cheap cards no longer round to $0.00; "Played" grade multiplier added
- [x] eBay Marketplace Account Deletion webhook (compliance, on Render)

### Identification & Grading
- [x] Claude vision identification; prompt tuned for vintage MTG ("Summon X")
- [x] Game name no longer leaks into set field
- [x] Inspector recalibrated — relative (not absolute) defect detection;
      fixed white-border false positives and the off-centering 0.00 bug
- [x] Re-identify Selected — re-reads saved scans with improved prompt

### Import & Scanning
- [x] Parallel batch review (process all, then one review table)
- [x] Rotate / 90° / deskew controls (scan + batch review + card detail)
- [x] Scanner quality fix — disabled JPEG compression, denoise-first pipeline
- [x] Front/back pairing: sequential, by filename, and by orientation
- [x] PDF import (pypdfium2) — multi-page and single-page
- [x] Watch folder auto-import on a schedule (daily / interval)
- [x] Duplicate cards merge into one row (auto + "Merge Duplicates" button)

### Collection
- [x] Editable card detail dialog (fields + image rotation, persisted)
- [x] Sortable columns (click headers; numeric/date aware)
- [x] Scan-order preserved (id tiebreaker on same-second saves)
- [x] Re-value moved to background thread

### Security & Config
- [x] Brute-force lockout on login
- [x] TOTP secret encrypted at rest (Fernet); recovery codes hashed
- [x] Input validation before every DB insert/update; update_card no longer clobbers
- [x] Specific exception handlers in core modules (no bare except)
- [x] User-supplied API keys via encrypted Settings screen + first-run prompt

---

## 🎯 Remaining path to Microsoft Store

### 1. Logging (required — packaged apps have no console) ✅ DONE
- [x] Central `core/logging_config.py` — rotating file in
      `%APPDATA%/TradingCardManager/logs/app.log` (+ console in dev)
- [x] All app `print()` calls replaced with module loggers
      (only the dev-only `apply-fixes.py` still prints)

### 2. Privacy policy (required for Store listing)
- [ ] Write and host a privacy policy (data stored locally; images sent to
      Anthropic/eBay; Windows Hello biometrics; no eBay user data stored)

### 3. Packaging
- [ ] PyInstaller build → standalone `.exe` (bundle Tesseract + VC runtimes)
- [ ] Wrap in MSIX; pass Windows App Certification Kit (WACK)
- [ ] Store assets: icon set, screenshots, description, age rating

### 4. Pre-release hardening
- [ ] Unit tests for `database`, `valuator`, `auth`, `inspector`, pairing logic
- [ ] Graceful "no API key" degradation messaging throughout
- [ ] Remove dev artifacts from the package (`.env`, `apply-fixes.py`)

---

## 🔵 Low Priority / Polish
| # | Item | Location |
|---|------|----------|
| P-2 | A few unpinned `>=` versions in requirements | `requirements.txt` |
| P-4 | Windows Hello has no guaranteed password fallback path | `core/auth.py` |
| P-6 | Wrong filename in file header comment | `reports_generator.py:1` |
| P-7 | Add "Star Wars" / "Non-Sport" to the game list for tighter valuation | `identifier.py`, UI combos |
| P-8 | Reports stats-bar emojis render as placeholders on some systems | `ui/reports_tab.py` |

---

## 💭 Possible future features
- Pokémon pricing via pokemontcg.io (free API), like Scryfall for MTG
- Background watch service (import even when the app is closed)
- TradingCardAPI.com integration (when beta access arrives)
- Managed/proxy API tier (if going freemium instead of bring-your-own-key)

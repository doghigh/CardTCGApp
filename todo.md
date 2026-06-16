# Lorebox — TODO

**Repository:** https://github.com/doghigh/CardTCGApp  (private)
**Last updated:** 2026-06-16
**Branch:** main
**Goal:** Ship to the Microsoft Store

---

## 🏪 Microsoft Store status
- ✅ Developer account **reinstated** (was deactivated; reactivated via reportap@microsoft.com).
- ⏰ **Must publish within 90 days** of reinstatement to keep the account active.
- Registration is now **free** (no $19 fee).
- After publishing, migrate identity from `catsjc1175@hotmail.com` →
  `jcatlowdev@outlook.com` (separate MSA — support request, do it *after* launch).

### Licensing & Store-agreement compliance (reviewed against ADA v8.11)
- [x] **Open source — AGPL-3.0** (`LICENSE`). Resolves PyQt6's GPL obligation
      (shipping on PyQt6 requires GPL-compatible licensing OR a commercial Qt
      license; open-sourcing satisfies it). Author retains copyright (commercial
      dual-licensing stays possible).
- [x] **Retired PriceCharting web scrape** — valuation now uses official APIs
      only (Scryfall + eBay Browse); avoids ToS/indemnification exposure.
      `search_pricecharting()` is a safe no-op. TradingCardAPI to be added later.
- [x] Privacy policy exists (`PRIVACY.md` + Render `/privacy`); affiliation
      disclaimer in README + privacy policy.
- [ ] **Store listing screenshots** must use non-branded/your-own cards (don't
      feature Topps/Pokémon/Magic art as the hero image). — your task
- [ ] **Website** on loreboxapp.dev hosting privacy + contact info. — your task
- [ ] Put privacy-policy URL + contact email in the Store listing fields.

### Remaining path to submission (needs you)
- [ ] **Decide the final product name / branding** — reserve it in Partner Center
      (gives the Identity Name + Publisher ID). One-line change in
      `packaging/AppxManifest.xml` + rerun `assets/generate_assets.py` (or drop in
      a real logo with the same filenames).
- [ ] Fill `AppxManifest.xml` Identity/Publisher from Partner Center.
- [ ] Build MSIX: `pyinstaller Lorebox.spec --noconfirm` →
      `packaging/build_msix.ps1` (needs Windows SDK / `makeappx`).
- [ ] Pass **WACK** (Windows App Certification Kit).
- [ ] Store listing: screenshots, description, category, age rating.
- [ ] Confirm privacy policy URL live + swap `[YOUR-CONTACT-EMAIL]` in PRIVACY.

---

## ✅ Completed this session (code review pass)

### Performance
- [x] **Deskew optimized** — angle is now detected on a downscaled copy
      (≤1000 px) before any full-res warp; already-straight scans early-out with
      no `warpAffine`. Big batch-import win on high-DPI scans. (#3, #7)
- [x] **add_card single connection** — duplicate check + insert/update now share
      one connection instead of opening two per card (batch-insert win). (#5)
- [x] Regression tests added for image_ops (now 43 tests total).

### Polish
- [x] **"Non-Sport" game category** added (scan, batch, detail, vision prompt) —
      Star Wars / Garbage Pail Kids / Marvel etc. classify correctly and route to
      an all-category eBay search. (P-7)
- [x] **requirements pinned** — `anthropic==0.105.2`; **removed unused
      paddleocr/paddlepaddle** (never imported; slims install). (P-2)
- [x] P-6 (reports_generator header) — verified correct, not an issue.

---

## ✅ Completed (earlier sessions)

### Store-readiness
- [x] Logging — rotating file at `%APPDATA%/Lorebox/logs/app.log`
- [x] Privacy policy — `PRIVACY.md` + hosted at Render `/privacy`; Help menu link
- [x] PyInstaller standalone windowed exe (onedir; see BUILD.md)
- [x] App icon set + MSIX tiles (`assets/generate_assets.py`)
- [x] MSIX manifest + pack script (`packaging/`)
- [x] Unit tests (`tests/`, stdlib unittest) — run `python -m unittest discover -s tests`
- [x] In-app Help Center (F1) — 16 searchable topics, offline

### Features
- [x] Dashboard — KPIs, value-over-time chart, game/grade bars, set completion,
      clickable nav, top/recent tables
- [x] Custom accent themes (40 presets + custom + extract-from-card)
- [x] Accessibility — text size, high-contrast, keyboard focus, SR labels
- [x] Valuation — Scryfall (MTG) + eBay Browse + PriceCharting fallback
- [x] Identification (Claude vision) + condition grading + re-identify
- [x] Batch import (folder + PDF), front/back pairing modes, watch folder
- [x] Duplicate auto-merge + "Merge Duplicates"; editable card detail
- [x] Security — login lockout, encrypted TOTP, input validation, user API keys

---

## ⚡ Performance — evaluated, deferred (with rationale)

These were flagged but are **premature at the expected scale** for a single-user
SQLite desktop app (queries on even 5k rows run in single-digit ms). Revisit only
if a genuinely large collection shows lag. Documented so the analysis isn't lost.

| # | Item | Why deferred |
|---|------|--------------|
| 1 | Pagination for `get_all_cards()` | It's one query, not N+1. Real cost is rendering thousands of rows in `QTableWidget` — a UI rewrite to `QTableView`+model. Worth it only past ~5k cards. |
| 2 | LIKE → FTS5 search | LIKE on a few-thousand-row table is sub-10ms. FTS5 adds a schema + sync layer; not worth the regression risk yet. |
| 4 | Unbounded image memory in batch review | Real, but the fix (reload thumbs on demand) is a sizable refactor; batches are typically small. Revisit if 100+‑card batches OOM. |
| 8 | Merge-duplicates loads full table | Only runs on an explicit button press, rarely. SQL GROUP BY rewrite is risky for marginal gain. |
| 9 | Daily snapshot full scan | One indexed aggregate, once/day. Negligible. |
| 10/12 | Dashboard aggregation cache | Each aggregate is a fast scan; refresh is on tab-switch only. Caching adds stale-data risk. |
| 11 | Thumbnail conversion in display loop | Generated once per populate, not in a hot loop. Low impact. |

---

## 🔵 Remaining polish
| # | Item | Location |
|---|------|----------|
| P-4 | Windows Hello has no guaranteed password fallback path | `core/auth.py` |
| P-8 | Reports stats-bar emojis render as placeholders on some systems | `ui/reports_tab.py` |
| — | Graceful "no API key" messaging is handled by the first-run prompt + Settings; could add an inline banner on the Scan tab when no key is set | `ui/scan_tab.py` |

---

## 💭 Possible future features
- Pokémon pricing via pokemontcg.io (free API), like Scryfall for MTG
- Background watch service (import even when the app is closed)
- CardChain MCP comparison data (dev-time only; connected in Claude Code)
- Managed/proxy API tier (if going freemium instead of bring-your-own-key)

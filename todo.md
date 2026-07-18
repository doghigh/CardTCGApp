# Lorebox — TODO

**Repository:** https://github.com/doghigh/CardTCGApp  (**public**)
**Last updated:** 2026-07-06 (code review pass)
**Branch:** main
**Version:** 1.2.0.0 (LAN sync release)
**Goal:** ~~Ship to the Microsoft Store~~ **Shipped** — [live listing](https://apps.microsoft.com/store/detail/9N94V4458M3V).
Focus now: post-launch polish + the Android companion app / LAN sync loop.

---

## 🏪 Microsoft Store status
- ✅ **Published and live** — `packaging/AppxManifest.xml` is at `Version="1.2.0.0"`,
  Identity/Publisher are filled in (`33303JesseCatlow.Lorebox`), and the site's
  "Get it on the Microsoft Store" buttons point at a real listing ID. All of the
  "remaining path to submission" items from the last pass (product name, MSIX
  build, WACK, listing screenshots) are done.
- ⚠️ **Unverified — no commit trail:** identity migration from
  `catsjc1175@hotmail.com` → `jcatlowdev@outlook.com` was planned for
  *after* launch. Nothing in git/docs confirms it happened — check Partner
  Center directly.
- [x] `PRIVACY.md` placeholder `[YOUR-CONTACT-EMAIL]` swapped for
      `contact@loreboxapp.dev`, matching the live site's privacy page
      (`site/privacy.html:109`).

### Licensing & Store-agreement compliance (reviewed against ADA v8.11)
- [x] **Open source — AGPL-3.0** (`LICENSE`).
- [x] **Retired PriceCharting web scrape** — valuation uses official APIs only
      (Scryfall + eBay Browse); `search_pricecharting()` is a safe no-op.
      TradingCardAPI still noted as a future source, not yet added.
- [x] Privacy policy exists (`PRIVACY.md` + site `/privacy.html`); affiliation
      disclaimer in README + privacy policy.
- [x] Store listing screenshots — trademark-free demo data (`screenshots/sc1-4.png`).
- [x] Website live at loreboxapp.dev with privacy + (real) contact info.
- [ ] Confirm privacy-policy URL + contact email are filled into the actual
      Partner Center listing fields (can't verify from the repo).

---

## ✅ Completed since last pass (LAN sync + pairing + site relaunch)

### LAN sync (phone → PC)
- [x] `core/sync_server.py` — stdlib `http.server` receiver, bearer-token auth,
      idempotent ingest (no Flask dependency).
- [x] `core/` LAN IP detection + persistent sync token in config.
- [x] `ui/sync_receive_dialog.py` — "Receive from phone" dialog + menu action;
      per-card ack deletes the source photo off the phone.
- [x] Live UI refresh wired up — collection/dashboard/reports update as cards
      arrive, instead of needing F5/restart.
- [x] `db`: phone-provided `defects_json` persists on sync (back-compat with
      the older `defects` list field).
- [x] `tests/test_sync_server.py`, `tests/test_sync_token.py` added.
- [x] Companion mobile-side work tracked in the LoreBox-Mobile repo (merged).

### Pairing / provisioning
- [x] **Pair-phone QR dialog** (`ui/dialogs.py` / `pair_dialog.py`) for Android
      key provisioning, reusing the same pairing infra as LAN sync's QR connect.
- [x] Pair-phone QR fixed to source API keys from `.env`, not just the saved
      config file (was silently omitting keys set only via `.env`).
- [x] Brute-force lockout state now persists across app restarts
      (`core/auth.py`).

### Marketing site (loreboxapp.dev)
- [x] Landing page redesign ("The Slab"), SEO/meta (OG, Twitter Card, JSON-LD,
      canonical, touch icon), 480px breakpoint, a11y pass.
- [x] Bulk-scanning section + downloadable card-jig STL.
- [x] "Choosing a scanner" pricing-tier comparison section.
- [x] "Before You Start" BYO-keys (Anthropic + eBay) setup section.
- [x] Removed misleading "Cert 0001 2026" grading-style label from the hero card.
- [x] "Scanning" added to top nav.

---

## ✅ Completed — prior code review pass

### Performance
- [x] **Deskew optimized** — angle is now detected on a downscaled copy
      (≤1000 px) before any full-res warp; already-straight scans early-out with
      no `warpAffine`. Big batch-import win on high-DPI scans. (#3, #7)
- [x] **add_card single connection** — duplicate check + insert/update now share
      one connection instead of opening two per card (batch-insert win). (#5)
- [x] Regression tests added for image_ops (43 tests then; **51 tests now**
      with the LAN sync suite — `python -m pytest tests/` all passing).

### Polish
- [x] **"Non-Sport" game category** added (scan, batch, detail, vision prompt) —
      Star Wars / Garbage Pail Kids / Marvel etc. classify correctly and route to
      an all-category eBay search. (P-7)
- [x] **requirements pinned** — `anthropic==0.105.2`; **removed unused
      paddleocr/paddlepaddle** (never imported; slims install). (P-2)
- [x] P-6 (reports_generator header) — verified correct, not an issue.
- [x] **P-4 re-checked** — `LoginDialog._build_ui()` always creates the password
      field before `_attempt_hello()` runs; Windows Hello failing/unavailable
      just leaves the normal password form up. Fallback path is guaranteed —
      closing this out rather than leaving it in "remaining polish".

---

## ✅ Completed (earlier sessions)

### Store-readiness
- [x] Logging — rotating file at `%APPDATA%/Lorebox/logs/app.log`
- [x] Privacy policy — `PRIVACY.md` + hosted at Render `/privacy`; Help menu link
- [x] PyInstaller standalone windowed exe (onedir; see BUILD.md)
- [x] App icon set + MSIX tiles (`assets/generate_assets.py`)
- [x] MSIX manifest + pack script (`packaging/`)
- [x] Unit tests (`tests/`) — run `python -m pytest tests/` (51 tests). Plain
      `unittest discover` still works but only picks up 43 — the two sync test
      files (`test_sync_server.py`, `test_sync_token.py`) are pytest-style,
      not `unittest.TestCase`.
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

## 🔵 Remaining polish — all closed out this pass
- [x] **P-8** — removed the header/stats-bar emoji (📊 📄 🃏 💰 🧾 📈) from
      `ui/reports_tab.py` that rendered as placeholder boxes on some systems;
      plain text labels instead.
- [x] **Scan-tab "no API key" banner** — added. `ScanTab` now shows a dismiss-free
      warning banner ("No Anthropic API key set…") with a **Set Up Key…** button
      whenever `ANTHROPIC_API_KEY` isn't set; emits `open_settings_requested`,
      wired to `MainWindow._open_settings` in `ui/main_window.py`, and refreshes
      itself right after the Settings dialog closes.
- [x] `PRIVACY.md` contact-email placeholder — done (see Store status above).

### Repo hygiene — all closed out this pass
- [x] `.github/workflows/prompt_eval.yml` — removed. It referenced files that
      don't exist in this repo (`output/perplexity_god_mode_v4.py`, etc.),
      copied from an unrelated project template.
- [x] `screenshots/New Python.File.py` — deleted (was empty).
- [x] `site/businessplan.md`, `site/businessplan2.md`,
      `screenshots/LoreBox_Business_Plan.docx` — moved out of the repo
      entirely to OneDrive/LoreBox/business; defunct `.gitignore` rules for
      them removed too.

---

## 🎯 Backlog — queued features (2026-07-18)
- [ ] **Custom game categories** — let users add their own games instead of
      falling back to "Other"/"Non-Sport". Needs a small custom-games store
      (config/prefs), surfaced in the game dropdowns (`ui/dialogs.py`,
      `ui/batch_review_dialog.py` `GAMES`) + a Settings manager. (Vision prompt
      enum stays fixed; users re-label after, or we extend the prompt later.)
- [ ] **Estimated-spend counter + billing link (dashboard)** — Anthropic has
      NO API to read a key's real balance (Console-only, like the OAuth wall).
      Buildable version: a dashboard tile "~$X.XX estimated this month" from the
      identification count (≈$0.006/card) + a "View billing" button deep-linking
      to console.anthropic.com. NOT a real balance — an estimate.
- [ ] **De-slop pass (site + app)** — remove AI-generated-slop signals: the
      color scheme, the "tagging"/marketing paragraphs that read as AI-written,
      and any generic filler copy. Make the landing page + in-app copy read as
      human-authored and credible. (Site: `site/`; app: banners, help text,
      dialog copy.)

## 💭 Possible future features
- Pokémon pricing via pokemontcg.io (free API), like Scryfall for MTG
- Background watch service (import even when the app is closed)
- CardChain MCP comparison data (dev-time only; connected in Claude Code)
- Managed/proxy API tier (if going freemium instead of bring-your-own-key)

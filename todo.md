---

## ⚡ Performance Issues (Identified 2026-06-14)

### 🔴 **Critical Performance Issues**

**1. Database N+1 Query Pattern — `get_all_cards()`** (`core/database.py:347–363`)
- **Issue:** Loading ALL cards into memory on every collection view access
- **Impact:** 1000+ cards = UI lag, memory bloat, wasted I/O
- **Code:**
```python
def get_all_cards(self, search: str = None) -> List[Dict]:
    rows = conn.execute("SELECT * FROM cards ORDER BY updated_at DESC, id ASC").fetchall()
    return [dict(r) for r in rows]  # Entire table loaded
```
- **Fix:** Implement pagination (LIMIT/OFFSET) or lazy loading; load only visible page
- **Priority:** HIGH — affects every collection view

**2. LIKE Searches Bypass Indexes** (`core/database.py:354–358`)
- **Issue:** `WHERE name LIKE ? OR set_name LIKE ?` with leading `%` forces full table scan
- **Impact:** Search slowness on 5000+ cards
- **Code:**
```python
term = f"%{search.strip()}%"
rows = conn.execute("""
    SELECT * FROM cards
    WHERE name LIKE ? OR set_name LIKE ? OR game LIKE ? OR card_number LIKE ?
    ORDER BY updated_at DESC, id ASC
""", (term, term, term, term)).fetchall()
```
- **Fix:** Use SQLite FTS5 (full-text search) or prefix-only matching (no leading `%`)
- **Priority:** HIGH — blocks search feature on large collections

**3. Batch Deskew on ALL Images** (`ui/batch_review_dialog.py:90–106`)
- **Issue:** Every card deskewed even if already straight; expensive CV ops (GaussianBlur, Otsu, minAreaRect, warpAffine)
- **Impact:** 30-card batch × 2–5 sec/card = 60–150 seconds total
- **Code:**
```python
def _process(self, idx: int, chunk: List[np.ndarray]) -> dict:
    chunk = [deskew(im) for im in chunk]  # Expensive for all cards
    info = self.identifier.identify_card(front, back)
    inspection = self.inspector.inspect(front)
    valuation = self.valuator.value_summary(...)
```
- **Fix:** Add skew-detection pre-check (simple threshold); cache/skip deskew for low angles
- **Priority:** HIGH — blocks batch import workflow

**4. Unbounded Memory in Batch Dialog** (`ui/batch_review_dialog.py:156–288`)
- **Issue:** All image arrays (50–100 MB each) held in memory during review phase
- **Impact:** 50 high-DPI scans × 2.5 MB = 125+ MB resident memory
- **Code:**
```python
self._results: dict[int, dict] = {}  # Stores ALL images until dialog closes
# Each row's `images` field contains full NumPy arrays
```
- **Fix:** Store only metadata; reload images on demand for thumbnails; compress/downsample in-memory cache
- **Priority:** MEDIUM

---

### 🟠 **High Priority Performance Issues**

**5. Duplicate Detection on Every Insert** (`core/database.py:181–201`)
- **Issue:** Each `add_card()` runs `find_duplicate()` before insert (extra query with complex IFNULL/LOWER logic)
- **Impact:** Batch insert of 30 cards = 30 finds + 30 inserts/updates = 60 round trips
- **Code:**
```python
def add_card(self, card: Dict, merge_duplicates: bool = True) -> int:
    card = self._validate_card(card)
    if merge_duplicates:
        dup_id = self.find_duplicate(card)  # <-- EXTRA QUERY
        if dup_id is not None:
            conn.execute("UPDATE cards SET quantity = quantity + ?...")
            return dup_id
    conn.execute("INSERT INTO cards ...")
```
- **Fix:** Use `INSERT OR IGNORE` + `ON CONFLICT UPDATE` or batch duplicate detection in-app
- **Priority:** HIGH — significant for batch operations

**6. Multiple Sequential API Calls per Card** (`ui/batch_review_dialog.py:98–106`)
- **Issue:** identify → inspect → valuate called sequentially (3 separate requests) per card with no caching
- **Impact:** If Anthropic + eBay APIs average 5 sec total per card, 30-card batch = 150 seconds
- **Code:**
```python
info = self.identifier.identify_card(front, back)        # API call 1
inspection = self.inspector.inspect(front)              # API call 2
valuation = self.valuator.value_summary(...)            # API call 3
```
- **Fix:** Batch API calls or implement result caching for duplicate cards
- **Priority:** HIGH — blocks batch import

**7. Expensive Deskew Operations** (`utils/image_ops.py:41–77`)
- **Issue:** cvtColor → GaussianBlur → threshold → Otsu → findNonZero → minAreaRect → warpAffine all called sequentially; no early exit
- **Impact:** 1–2 sec per image even if angle is < 0.3° (quick win)
- **Code:**
```python
gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
blurred = cv2.GaussianBlur(gray, (5, 5), 0)
_, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
# ... then expensive minAreaRect + warpAffine
```
- **Fix:** Quick histogram-based skew pre-check before expensive CV ops
- **Priority:** HIGH

---

### 🟡 **Medium Priority Performance Issues**

**8. Merge Duplicates Loads Full Table** (`core/database.py:232–296`)
- **Issue:** `SELECT * FROM cards` loads entire table to memory for deduplication
- **Impact:** Slow on 5000+ cards, high memory
- **Code:**
```python
def merge_existing_duplicates(self) -> Dict[str, int]:
    with self._lock, self._conn() as conn:
        rows = conn.execute("SELECT * FROM cards ORDER BY id ASC").fetchall()  # FULL TABLE
        groups: Dict[tuple, List] = {}
        for r in rows:
            key = (...)
            groups.setdefault(key, []).append(r)
```
- **Fix:** Use SQL GROUP BY + window functions to identify duplicates in-database
- **Priority:** MEDIUM

**9. Aggregate Queries Scan Full Table Daily** (`core/database.py:450–470`)
- **Issue:** `record_value_snapshot()` SUM/COUNT all cards every time (called daily)
- **Impact:** Full table scan × 90 snapshots = wasteful, especially with 5000+ cards
- **Code:**
```python
row = conn.execute("""
    SELECT COUNT(*) AS c, SUM(quantity), SUM(estimated_value * quantity)
    FROM cards  # <-- FULL TABLE
""").fetchone()
```
- **Fix:** Incremental snapshots or compute only on changed cards
- **Priority:** MEDIUM

**10. No Pagination in Dashboard/Reports** (`ui/collection_tab.py`, `ui/dashboard_tab.py`)
- **Issue:** All stats/breakdowns computed for full collection every view refresh
- **Impact:** Slow dashboard with 5000+ cards
- **Fix:** Add aggregation cache; refresh only on card add/edit
- **Priority:** MEDIUM

---

### 🔵 **Low Priority / Optimization Opportunities**

**11. Image Conversions in Display Loop** (`ui/batch_review_dialog.py:363–375`)
- **Issue:** `_make_thumb()` converts NumPy → QImage → QPixmap for every row (can be 50+ conversions)
- **Impact:** Noticeable lag when populating review table (50 rows)
- **Fix:** Cache converted thumbnails; generate once, reuse
- **Priority:** LOW

**12. No Query Result Caching** (throughout `core/database.py`)
- **Issue:** Same queries (e.g., `get_game_breakdown()`) called multiple times per view refresh
- **Impact:** Dashboard refresh re-computes all stats
- **Fix:** Add simple result cache with TTL (60 sec) or event-based invalidation
- **Priority:** LOW

---

## 📋 **Performance Fixes (Recommended Priority)**

### Immediate (blocks workflows):
1. Add LIKE → FTS5 search conversion (#2) — unblocks search feature
2. Optimize batch deskew with pre-check (#3, #7) — unblocks batch import
3. Implement pagination for collection view (#1) — unblocks large collections

### High Priority:
4. Batch duplicate detection or INSERT OR CONFLICT (#5) — improve batch insert speed
5. Cache API results per batch (#6) — reduce API calls by 60%
6. Stream/pipeline API calls instead of sequential (#6) — reduce 150 sec → 30 sec batch time

### Medium Priority:
7. Reduce in-memory image storage in review dialog (#4) — free up 100+ MB
8. SQL GROUP BY for duplicate merge (#8) — speed up deduplication
9. Cache aggregation results (#9, #10, #12) — speed up dashboard

---

**Repository:** https://github.com/doghigh/CardTCGApp
**Last updated:** 2026-06-14
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
      and extract-color-from-card-image
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
- [x] PyInstaller build → standalone windowed `.exe` (onedir, ~290 MB).
      `pyinstaller TradingCardManager.spec --noconfirm` → dist/. Launches
      cleanly; see BUILD.md. Excludes unused paddle/matplotlib/etc.
- [ ] App icon set (.ico + Store tiles)
- [ ] Wrap in MSIX; pass Windows App Certification Kit (WACK)
- [ ] Store assets: screenshots, description, age rating

### 4. Pre-release hardening
- [x] Unit tests (`tests/`, stdlib unittest, 38 tests) — database, valuator,
      watcher schedule, theme, front/back pairing, inspector. Run with
      `python -m unittest discover -s tests`
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

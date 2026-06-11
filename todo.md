# Trading Card Manager — TODO

Now let me review this file in detail for security and robustness issues:

## 🔍 Security & Robustness Review: `core/reports_generator.py`

### 🔴 **Critical Issues**

**1. No Exception Handling for PDF Generation (`core/reports_generator.py:199`)**
- **Issue:** `doc.build(story)` can fail for various reasons (disk space, permissions, corrupted data), but there's no try-catch
- **Risk:** App crash with no user feedback
- **Code:**
```python
doc.build(story)  # Can raise exceptions but not caught
return out_path
```
- **Fix:**
```python
try:
    doc.build(story)
except Exception as e:
    logger.error(f"Failed to build PDF: {e}")
    raise ReportGenerationError(f"Failed to generate PDF: {str(e)}")
```

**2. No Validation of Input Parameters (`core/reports_generator.py:36`)**
- **Issue:** Year and month are not validated
- **Risk:** Invalid months (13+) or negative years could cause crashes
- **Code:**
```python
def generate_monthly(self, year: int, month: int) -> Optional[Path]:
    start = datetime(year, month, 1)  # Will crash if month > 12 or < 1
```
- **Fix:**
```python
def generate_monthly(self, year: int, month: int) -> Optional[Path]:
    if not isinstance(year, int) or not isinstance(month, int):
        raise ValueError("Year and month must be integers")
    if not (1 <= month <= 12):
        raise ValueError(f"Month must be 1-12, got {month}")
    if year < 1900 or year > datetime.now().year + 1:
        raise ValueError(f"Invalid year: {year}")
```

**3. Unsafe String Truncation in Report Data (`core/reports_generator.py:128-132`)**
- **Issue:** Slicing strings `[:30]`, `[:20]` could split multi-byte UTF-8 characters
- **Risk:** Corrupted card names in PDF
- **Code:**
```python
(c.get('name') or '')[:30],  # Could split UTF-8 chars
(c.get('set_name') or '')[:20],
```
- **Fix:**
```python
def truncate_utf8(text: str, max_len: int) -> str:
    text = text or ''
    encoded = text.encode('utf-8')
    if len(encoded) <= max_len:
        return text
    truncated = encoded[:max_len]
    # Remove incomplete UTF-8 sequences
    while truncated:
        try:
            return truncated.decode('utf-8')
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return ''
```

---

### 🟠 **High Priority Issues**

**4. No File Permissions Validation (`core/reports_generator.py:56-58`)**
- **Issue:** Creates directory without checking if write permission exists
- **Risk:** Silent failure or crashes during PDF write
- **Code:**
```python
reports_dir = APP_DIR / "reports"
reports_dir.mkdir(parents=True, exist_ok=True)
out_path = reports_dir / f"collection_report_{year}_{month:02d}.pdf"
```
- **Fix:**
```python
reports_dir = APP_DIR / "reports"
try:
    reports_dir.mkdir(parents=True, exist_ok=True)
    # Test write permission
    test_file = reports_dir / ".write_test"
    test_file.touch()
    test_file.unlink()
except (OSError, PermissionError) as e:
    logger.error(f"Cannot write to reports directory: {e}")
    return None
```

**5. Database Save Called After PDF Build, No Rollback (`core/reports_generator.py:202-208`)**
- **Issue:** If PDF is created successfully but database save fails, inconsistency occurs
- **Risk:** Report exists but not recorded in database
- **Code:**
```python
doc.build(story)  # Creates file
self.db.save_report(...)  # Could fail, file orphaned
```
- **Fix:**
```python
try:
    doc.build(story)
    self.db.save_report(...)
except Exception as e:
    # Try to clean up
    try:
        out_path.unlink()
    except:
        pass
    raise
```

**6. No Input Sanitization for HTML in Paragraph (`core/reports_generator.py:117-120`)**
- **Issue:** Card data is inserted into HTML strings without escaping
- **Risk:** If card names contain `<b>`, `<br/>`, or HTML tags, could corrupt PDF layout
- **Code:**
```python
story.append(Paragraph(
    f"Cards added: <b>{len(period_cards)}</b><br/>"
    f"Value added: <b>${period_value:,.2f}</b>",
    styles['Normal']
))
```
- **Fix:**
```python
from html import escape
story.append(Paragraph(
    f"Cards added: <b>{len(period_cards)}</b><br/>"
    f"Value added: <b>{escape(f'${period_value:,.2f}')}</b>",
    styles['Normal']
))
```

**7. No Handling for Division by Zero or None Values (`core/reports_generator.py:114, 149)`**
- **Issue:** Calculations assume values are numeric
- **Risk:** TypeError if database returns None or unexpected types
- **Code:**
```python
period_value = sum((c.get('estimated_value') or 0) * (c.get('quantity') or 1) for c in period_cards)
# If quantity is None, `or 1` works, but if it's 0, calculations fail
```
- **Fix:**
```python
def safe_get_numeric(obj: dict, key: str, default: float = 0) -> float:
    val = obj.get(key, default)
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default

period_value = sum(
    safe_get_numeric(c, 'estimated_value') * safe_get_numeric(c, 'quantity', 1) 
    for c in period_cards
)
```

**8. No Timestamp Validation (`core/reports_generator.py:49-50`)**
- **Issue:** Date strings passed to database without format validation
- **Risk:** If database returns malformed timestamps, report generation could fail
- **Code:**
```python
period_cards = self.db.get_cards_for_period(
    start.strftime('%Y-%m-%d %H:%M:%S'),
    end.strftime('%Y-%m-%d %H:%M:%S')
)
```

---

### 🟡 **Medium Priority Issues**

**9. Bare Exception Handling (`core/reports_generator.py:22-23`)**
- **Issue:** ImportError silently sets flag, but no user feedback
- **Location:** `try/except` for reportlab import
- **Fix:**
```python
try:
    from reportlab.lib.pagesizes import letter
    # ... other imports
    HAS_REPORTLAB = True
except ImportError as e:
    logger.warning(f"ReportLab not installed: {e}")
    HAS_REPORTLAB = False
```

**10. No Logging of Report Generation (`core/reports_generator.py:36-210`)**
- **Issue:** No audit trail of reports generated
- **Risk:** Cannot troubleshoot or track report history
- **Fix:**
```python
def generate_monthly(self, year: int, month: int) -> Optional[Path]:
    logger.info(f"Generating report for {year}-{month:02d}")
    try:
        # ... generate report
        logger.info(f"Report generated successfully: {out_path}")
        return out_path
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise
```

**11. Hardcoded Color Values Without Validation (`core/reports_generator.py:74, 79, 105, etc.)**
- **Issue:** Hex colors passed to reportlab without validation
- **Risk:** Invalid hex colors could cause crashes
- **Code:**
```python
textColor=colors.HexColor('#1a365d')
```
- **Fix:**
```python
def validate_hex_color(hex_color: str) -> bool:
    import re
    return bool(re.match(r'^#[0-9a-fA-F]{6}$', hex_color))

COLORS = {
    'dark_blue': '#1a365d',
    'medium_blue': '#2c5282'
}
for color in COLORS.values():
    if not validate_hex_color(color):
        raise ValueError(f"Invalid hex color: {color}")
```

**12. No Check for Empty Cards/Stats Before PDF Generation (`core/reports_generator.py:52-53)`**
- **Issue:** If database is empty, some tables might be empty but PDF still generated
- **Risk:** Confusing empty reports
- **Fix:**
```python
all_cards = self.db.get_all_cards()
stats = self.db.get_collection_stats()
if not all_cards or not stats:
    logger.warning("No cards in database, skipping report generation")
    return None
```

**13. Unsafe Path Construction for Report Filename (`core/reports_generator.py:58`)**
- **Issue:** Filename uses user-provided year/month without validation
- **Risk:** Could create unexpected filenames (though limited by datetime validation)
- **Fix:**
```python
out_path = reports_dir / f"collection_report_{year:04d}_{month:02d}.pdf"
# Ensure it's a valid path
if not out_path.parent.exists():
    raise ValueError("Report directory doesn't exist")
```

**14. No Handling for Large Collections (`core/reports_generator.py:125-141, 147-175)`**
- **Issue:** Limits data to 30 cards this month and 25 overall, but no clear reason
- **Risk:** Reports incomplete, no warning to user
- **Fix:**
```python
# Add documentation/configurable limits
MAX_MONTHLY_CARDS = 30
MAX_TOP_CARDS = 25

for c in period_cards[:MAX_MONTHLY_CARDS]:
    # ...

logger.debug(f"Showing {min(len(period_cards), MAX_MONTHLY_CARDS)} of {len(period_cards)} cards this month")
```

**15. No Validation That Database Methods Return Expected Types (`core/reports_generator.py:48-53)`**
- **Issue:** No assertion that returned values are lists/dicts
- **Risk:** Type errors if database API changes
- **Fix:**
```python
period_cards = self.db.get_cards_for_period(start_str, end_str)
assert isinstance(period_cards, list), "Database returned non-list for period_cards"
all_cards = self.db.get_all_cards()
assert isinstance(all_cards, list), "Database returned non-list for all_cards"
stats = self.db.get_collection_stats()
assert isinstance(stats, dict), "Database returned non-dict for stats"
```

---

### 🔵 **Low Priority Issues**

**16. Magic Numbers Without Constants (`core/reports_generator.py`)**
- **Issue:** Numbers like `0.2 * inch`, `3*inch` hardcoded
- **Locations:** Lines 87, 89, 111, 121, 134, 167, 189
- **Fix:**
```python
# At top of class
SPACING_SMALL = 0.2 * inch
SPACING_NORMAL = 0.3 * inch
COLUMN_NAME = 2.2 * inch
COLUMN_SET = 1.6 * inch
# ... etc
```

**17. Inconsistent Naming Convention (`core/reports_generator.py:103, 134, 167, 189`)**
- **Issue:** `colWidths` is camelCase, rest of code is snake_case
- **Risk:** Minor - style inconsistency
- **Fix:** Use snake_case consistently

**18. No Docstrings for Helper Logic**
- **Issue:** Complex calculations lack documentation
- **Location:** Lines 147-150 sorting logic
- **Fix:** Add docstrings explaining sorting and filtering

**19. No Context Manager for Database (`core/reports_generator.py:33-34`)**
- **Issue:** Database object stored but not guaranteed cleanup
- **Risk:** Minor - but could leave connections open
- **Fix:**
```python
try:
    report = ReportGenerator(db)
    report.generate_monthly(2026, 6)
finally:
    db.close()  # Ensure cleanup
```

---

## ✅ **Strengths**

- ✅ Uses pathlib for cross-platform path handling
- ✅ Creates reports directory safely with `mkdir(parents=True, exist_ok=True)`
- ✅ Uses parameterized queries for database save
- ✅ Good table formatting with TableStyle
- ✅ Calculates condition distribution dynamically
- ✅ Includes net position calculation

---

## 📋 **Recommended Fixes (Priority Order)**

### Immediate (Critical):
1. Add exception handling for `doc.build()` (#1)
2. Validate input parameters (year/month) (#2)
3. Add HTML escaping for card data (#6)
4. Add file permission validation (#4)

### High Priority:
5. Handle database save failure with rollback (#5)
6. Add safe numeric conversions (#7)
7. Add logging (#10)

### Medium Priority:
8. Improve error messages and validation (#9, #12, #15)
9. Add constants for magic numbers (#16)
10. Add docstrings (#18)

Would you like me to create a patch file with fixes for the critical issues, or add them to your `todo.md`?

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

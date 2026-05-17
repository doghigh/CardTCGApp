# Trading Card Manager - Code Review TODO

**Repository:** https://github.com/doghigh/CardTCGApp

---

## 🔴 **Runtime Crash Bugs** *(App will not run until these are fixed)*

### BUG-1. `LoginDialog` Not Defined — App Crashes on Startup (`ui/main_window.py:15`)
- **Issue:** `LoginDialog` is imported from `core.auth` but is never defined there.
- **Error:** `ImportError: cannot import name 'LoginDialog' from 'core.auth'`
- **Fix:** Add `LoginDialog` class to `core/auth.py` or change the import to wherever it is actually defined.

### BUG-2. Wrong Module Name for Report Generator (`ui/reports_tab.py:12`)
- **Issue:** Imports `from core.report_generator import ReportGenerator` but the file is `core/reports_generator.py` (with an extra `s`).
- **Error:** `ModuleNotFoundError: No module named 'core.report_generator'`
- **Fix:** Change import to `from core.reports_generator import ReportGenerator`

### BUG-3. `os` Not Imported in `reports_tab.py` (`ui/reports_tab.py:81,92`)
- **Issue:** `os.startfile(str(path))` is called in `_generate_report` and `_open_report` but `os` is never imported.
- **Error:** `NameError: name 'os' is not defined`
- **Fix:** Add `import os` at the top of `ui/reports_tab.py`

### BUG-4. `APP_DIR` Not Defined in Report Generator (`core/reports_generator.py:40`)
- **Issue:** `reports_dir = APP_DIR / "reports"` uses `APP_DIR` but it is never imported or defined in this file.
- **Error:** `NameError: name 'APP_DIR' is not defined`
- **Fix:** Add at the top of file:
```python
import os
from pathlib import Path
APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager"
```

### BUG-5. SyntaxError in `dialogs.py` on Python 3.11 (`ui/dialogs.py:65-67`)
- **Issue:** Backslash `\n` used inside f-string `{}` expression, which is invalid on Python < 3.12. Since `__pycache__` shows `cpython-311`, this will crash at import time for the entire module, taking down both `main_window.py` and `batch_tab.py` with it.
- **Error:** `SyntaxError: f-string expression part cannot include a backslash`
- **Affected lines:**
```python
# BROKEN on Python 3.11:
<pre>{"\n".join([f"• {d.get('type')} @ {d.get('location')}" for d in defects]) or "None"}</pre>
<pre>{"\n".join([f"• {v['source']}: ${v['value']}" for v in valuations]) or "None"}</pre>
```
- **Fix:** Extract the join to a variable before the f-string:
```python
defect_lines = "\n".join(f"• {d.get('type')} @ {d.get('location')}" for d in defects) or "None"
val_lines = "\n".join(f"• {v['source']}: ${v['value']}" for v in valuations) or "None"
info.setHtml(f"""
    ...
    <pre>{defect_lines}</pre>
    ...
    <pre>{val_lines}</pre>
""")
```

### BUG-6. `CsvMappingDialog` Not Defined (`ui/dialogs.py`, `ui/batch_tab.py:274`)
- **Issue:** `from ui.dialogs import CsvMappingDialog` in `batch_tab.py` but `CsvMappingDialog` is never defined in `dialogs.py`.
- **Error:** `ImportError: cannot import name 'CsvMappingDialog' from 'ui.dialogs'`
- **Fix:** Implement `CsvMappingDialog` in `ui/dialogs.py` (a dialog that maps CSV column headers to card fields).

### BUG-7. `APP_DIR` Not Defined in `collection_tab.py` (`ui/collection_tab.py:138`)
- **Issue:** `_export_csv` references `APP_DIR` as a default path but `APP_DIR` is never imported or defined in `ui/collection_tab.py`.
- **Error:** `NameError: name 'APP_DIR' is not defined`
- **Fix:** Add `APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager"` at the top of the file (it's already defined in `ui/collections.py` but not in `ui/collection_tab.py`).

### BUG-8. Ellipsis Literal Written to CSV (`ui/collection_tab.py:147`)
- **Issue:** `writer.writerow([c.get('id'), c.get('name'), c.get('set_name'), ...])` uses the Python `...` (Ellipsis) object as an argument. The remaining columns are never written; instead the string `"Ellipsis"` is written in the last cell.
- **Error:** Silent data corruption — CSV output is incomplete and malformed.
- **Fix:** Replace `...` with all actual column values matching the header row defined on line 145.

---

## 🔴 **Logic Errors**

### BUG-9. `update_card` Defects Branch Is Dead Code (`core/database.py:102-117`)
- **Issue:** The `if k == 'defects':` branch at line 112 is unreachable. The `allowed` set does not include `'defects'`, so any card with a `'defects'` key is already filtered out by `if k not in allowed: continue` on line 110-111. Defect data can never be updated via `update_card`.
- **Fix:** Add `'defects'` to the `allowed` set, or handle it before the loop:
```python
allowed = {'name', 'set_name', ..., 'defects'}
```

### BUG-10. Report PDF Body Is Empty (`core/reports_generator.py:54-55`)
- **Issue:** The story-building code is replaced with a comment `# ... (full story building code from earlier version)`. The generated PDF contains only a title and no actual card data.
- **Fix:** Implement the summary table, top cards list, and condition distribution sections.

### BUG-11. Zero Quantity Allowed in CSV Import (`ui/batch_tab.py:131`)
- **Issue:** `"quantity": int(get("quantity") or 1)` — if the CSV contains `"0"`, then `"0" or 1` evaluates to `"0"` (a non-empty string is truthy), so `int("0") = 0`. Cards with quantity 0 can be inserted.
- **Fix:**
```python
"quantity": max(1, int(get("quantity") or 1))
```

### BUG-12. Duplicate `CollectionTab` Class (`ui/collection_tab.py`, `ui/collections.py`)
- **Issue:** Both files define a `CollectionTab` class. `main_window.py` imports from `ui.collection_tab` (the broken version missing `APP_DIR` and with the `...` CSV bug). The complete version is in `ui/collections.py` but is never used.
- **Fix:** Delete `ui/collection_tab.py` and update the import in `main_window.py` to `from ui.collections import CollectionTab`.

### BUG-13. `_setup_menu` Is Empty (`ui/main_window.py:111-112`)
- **Issue:** `_setup_menu` contains only `pass`, so no File or Help menus are created despite the method being called in `__init__`.
- **Fix:** Implement the menu bar with File (Open Data Folder, Exit) and Help actions.

### BUG-14. Help Dialog Shows Placeholder Text (`ui/main_window.py:109`)
- **Issue:** `_show_help` displays `"..."` instead of actual keyboard shortcut documentation.
- **Fix:** Populate the help text with the full shortcuts table (Ctrl+1–4, Ctrl+N, Ctrl+F, Ctrl+S, F5, F1, Ctrl+Q).

---

## 🟠 **Critical Issues** *(Pre-existing, security-related)*

### 1. SQL Injection Vulnerability in Database Updates (`core/database.py:120`)
- **Issue:** Column names are interpolated directly into SQL string. While values are parameterized, malicious column names could cause issues.
- **Location:** `core/database.py`, `update_card()` method
- **Fix:** Use whitelist of allowed columns before interpolation
```python
ALLOWED_COLUMNS = {'name', 'set_name', 'card_number', 'rarity', 'game', 'year', 'language', 'foil', ...}
for k, v in updates.items():
    if k not in ALLOWED_COLUMNS:
        raise ValueError(f"Invalid column: {k}")
```
- **Priority:** HIGH - Do first

### 2. Insecure Password Storage (`core/auth.py:50`)
- **Issue:** Derived key is stored as-is. If someone gains access to `.auth.key`, they can use it directly without knowing the password.
- **Location:** `core/auth.py`, `set_password()` and `check_password()` methods
- **Fix:** Hash the derived key again for storage using SHA256
```python
def set_password(self, password: str):
    derived = self._derive_key(password)
    verification_hash = hashlib.sha256(derived).hexdigest()
    self.key_file.write_text(verification_hash)

def check_password(self, password: str) -> bool:
    stored_hash = self.key_file.read_text()
    derived = self._derive_key(password)
    verification_hash = hashlib.sha256(derived).hexdigest()
    return secrets.compare_digest(stored_hash, verification_hash)
```
- **Priority:** CRITICAL - Security vulnerability

### 3. ~~Weak Recovery Codes~~ (`core/auth.py:92`) — **FIXED**
- Current code already uses `secrets.token_hex(4).upper()`. Issue resolved.

### 4. No Input Validation for Card Data (`core/database.py:79-108`)
- **Issue:** No validation of data types, ranges, or string lengths before storage
- **Location:** `core/database.py`, `add_card()` method
- **Examples of missing validation:**
  - Card name can be any length or type
  - Year can be non-integer or out of reasonable range
  - Numeric fields (estimated_value, purchase_price) not validated
- **Fix:** Add validation before INSERT
```python
def add_card(self, card: Dict) -> int:
    name = card.get('name', 'Unknown')
    if not isinstance(name, str) or len(name) > 500:
        raise ValueError("Invalid card name")
    
    year = card.get('year')
    if year is not None:
        if not isinstance(year, int) or year < 1900 or year > datetime.now().year + 1:
            raise ValueError("Invalid year")
    # ... validate other fields
```
- **Priority:** HIGH - Data integrity and security

---

## 🟠 **High Priority Issues**

### 5. Bare Exception Handlers (Multiple Files)
- **Issue:** Catches all exceptions with bare `except:` or `except Exception:`, masking bugs and security issues
- **Locations:**
  - `core/auth.py:61` - `check_password()`
  - `core/valuator.py:38, 71, 96, 111` - Price fetching methods
  - `core/identifier.py:69` - `extract_text()`
  - `core/inspector.py` - Various detection methods
  - `core/scanner.py:51` - bare `except:` in `_auto_rotate()`
- **Fix:** Catch specific exceptions only
```python
# Instead of:
except Exception:
    pass

# Use:
except (ValueError, OSError, IOError) as e:
    logger.error(f"Failed to verify password: {e}")
    return False
```
- **Priority:** HIGH - Debugging and security

### 6. Hardcoded File Paths & Missing Validation (`core/identifier.py:22-39`)
- **Issue:** Windows-specific paths hardcoded, no validation after setting
- **Location:** `core/identifier.py`, `__init__()` method
- **Current Code:** Hardcoded paths like `r"C:\Program Files\Tesseract-OCR\tesseract.exe"`
- **Fix:** Validate Tesseract installation and test it
```python
import subprocess
def _validate_tesseract():
    try:
        result = subprocess.run([pytesseract.pytesseract.tesseract_cmd, '--version'], 
                              capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False
```
- **Priority:** HIGH - Robustness

### 7. Missing Rate Limiting in Web Scraping (`core/valuator.py:19-97`)
- **Issue:** No rate limiting, retry logic, or exponential backoff for external API calls
- **Risk:** Can trigger IP bans from TCGPlayer, eBay, PriceCharting
- **Location:** `core/valuator.py`, all `search_*` methods
- **Fix:** Add rate limiting and retry logic
```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def _create_session(self):
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
```
- **Priority:** HIGH - Can break functionality

### 8. Missing SSL Verification Explicit Setting (`core/valuator.py:24`)
- **Issue:** SSL verification not explicitly enabled (though default is True)
- **Location:** `core/valuator.py`, initialization and requests calls
- **Fix:** Explicitly set and handle SSL verification
```python
self.session.verify = True  # or use certifi
```
- **Priority:** MEDIUM - Security best practice

### 9. Fragile Web Scraping Parsing (`core/valuator.py:29-36`)
- **Issue:** Using regex and class patterns that will break if website HTML changes
- **Location:** All `search_*` methods
- **Fix:** Use more robust selectors or consider official APIs
- **Priority:** MEDIUM - Maintenance

### 10. File Path Traversal Risk (`ui/main_window.py:123`)
- **Issue:** Opening file system paths without validation
- **Location:** `ui/main_window.py`, `_setup_menu()` - `open_data` action
- **Current Code:** `os.startfile(str(APP_DIR))`
- **Fix:** Validate path before opening
```python
from pathlib import Path
def _open_data_folder():
    app_dir = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager"
    if app_dir.exists() and app_dir.is_dir():
        os.startfile(str(app_dir))
```
- **Priority:** MEDIUM - Path security

### 11. Unvalidated Scan File Paths (`core/database.py:38-39`)
- **Issue:** Scan paths stored without validation that files exist or are accessible
- **Location:** `core/database.py`, cards table schema
- **Fix:** Validate paths when storing and retrieving
```python
def add_card(self, card: Dict) -> int:
    front_path = card.get('front_scan_path')
    if front_path and not Path(front_path).exists():
        raise ValueError(f"Front scan path does not exist: {front_path}")
    # ...
```
- **Priority:** MEDIUM - Data integrity

---

## 🟡 **Medium Priority Issues**

### 12. Thread Safety Concerns (`core/database.py:14, 19`)
- **Issue:** Lock protects individual operations but transactions spanning multiple operations could have race conditions
- **Location:** `core/database.py`, Database class
- **Current Code:**
```python
self._lock = threading.Lock()
conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
```
- **Fix:** Consider using connection pooling or ensuring transactions are atomic
- **Priority:** MEDIUM - Concurrent access

### 13. No Logging Framework
- **Issue:** Using `print()` instead of Python's logging module
- **Locations:**
  - `main.py:45` - `print(f"{APP_NAME} v{APP_VERSION} started successfully!")`
  - `core/auth.py:161` - `print(f"Windows Hello error...")`
  - `core/identifier.py:71` - `print(f"OCR Error...")`
  - `core/scanner.py:105` - `print(f"Scan error: {e}")`
  - `core/scanner.py:120` - `print(f"File load error: {e}")`
- **Fix:** Implement logging
```python
import logging
logger = logging.getLogger(__name__)

# In main.py:
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(APP_DIR / 'app.log'),
        logging.StreamHandler()
    ]
)
logger.info(f"{APP_NAME} v{APP_VERSION} started successfully!")
```
- **Priority:** MEDIUM - Debugging and monitoring

### 14. Missing Dependency Version Pinning (`requirements.txt`)
- **Issue:** Loose version constraints can cause breaking changes
- **Current:** `PyQt6>=6.7.0`, `opencv-python>=4.10.0`
- **Fix:** Pin exact versions
```
PyQt6==6.7.0
opencv-python==4.10.0.84
numpy==1.26.4
Pillow==10.4.0
requests==2.32.0
beautifulsoup4==4.12.0
pytesseract==0.3.13
reportlab==4.2.0
cryptography==43.0.0
pyotp==2.9.0
qrcode[pil]==8.0
```
- **Priority:** MEDIUM - Reproducibility

### 15. Missing Error Messages for Users
- **Issue:** Many exceptions silently fail without user notification
- **Examples:**
  - Network timeouts in valuator
  - Missing Tesseract installation
  - Database connection errors
- **Fix:** Show user-friendly error dialogs
```python
QMessageBox.warning(self, "Error", f"Failed to fetch card value: {str(e)}")
```
- **Priority:** MEDIUM - User experience

### 16. No Rate Limiting for Database Operations
- **Issue:** High-frequency writes could overwhelm SQLite
- **Location:** `core/database.py`
- **Fix:** Consider write batching or connection pooling
- **Priority:** LOW - Depends on usage patterns

### 17. `_revalue_worker` Blocks the UI Thread (`ui/collections.py:161-171`)
- **Issue:** `_revalue_worker` runs synchronously on the main/UI thread via `QTimer.singleShot`, fetching web prices for every selected card in sequence. This freezes the UI for as long as the fetches take.
- **Fix:** Run re-valuation in a `QThread` similar to `_Worker` in `scan_tab.py`.
- **Priority:** MEDIUM - UX

### 18. Duplicate Tab Emoji in Main Window (`ui/main_window.py:63-64`)
- **Issue:** Both "Batch Import" and "Collection" tabs use the "📦" emoji, making them visually indistinguishable.
- **Fix:** Change one of the icons, e.g. Collection tab to "📋 Collection".
- **Priority:** LOW - UX

---

## 🔵 **Low Priority Issues**

### 19. Unused Import in `main.py` (`main.py:8`)
- **Location:** `from PyQt6.QtCore import Qt` — `Qt` is never used in `main.py`
- **Fix:** Remove the import
- **Priority:** LOW - Code cleanliness

### 20. Unused Import (`core/identifier.py:3`)
- **Location:** `import os` — only used indirectly through `os.environ.get` and `os.path.exists`; actually it IS used. But the comment in todo referred to it being unnecessary for other uses. Verify and clean up if truly unused.
- **Priority:** LOW - Code cleanliness

### 21. Windows Hello Auth Has No Fallback (`core/auth.py:121-146`)
- **Issue:** If Windows Hello fails, app could become inaccessible
- **Location:** `core/auth.py`, `request_biometric_login()`
- **Fix:** Ensure password fallback always works
- **Priority:** LOW - UX consideration

### 22. Missing Unit Tests
- **Issue:** No test coverage for security-critical functions
- **Examples:** Password verification, SQL queries, data validation
- **Priority:** LOW - Best practice

### 23. No Code Signing for Executable
- **Issue:** Distributed .exe should be signed for distribution
- **Location:** `build_exe.bat`
- **Priority:** LOW - Distribution security

### 24. File Comment Mismatch (`core/reports_generator.py:1`)
- **Issue:** File comment says `# core/report_generator.py` but the actual filename is `reports_generator.py`
- **Fix:** Update the comment to match the filename
- **Priority:** LOW - Code cleanliness

### 25. TOTP Secret Stored in Plaintext (`core/auth.py:79-81`)
- **Issue:** `.totp_secret` file is stored unencrypted on disk
- **Fix:** Encrypt using the derived key
- **Priority:** MEDIUM - Security best practice

---

## ✅ **Strengths to Maintain**

- ✅ Uses `secrets` module for salt and recovery code generation
- ✅ PBKDF2 with 600,000 iterations (good key derivation)
- ✅ Parameterized SQL queries (mostly correct)
- ✅ Foreign key constraints enabled
- ✅ Thread-safe database with locks
- ✅ Privacy-first design (local SQLite, no cloud)
- ✅ `update_card` has column whitelist (SQL injection mitigated)

---

## 📋 **Implementation Priority**

### Phase 0: Fix Crashes First (Nothing Runs Without These)
- [ ] Add `LoginDialog` to `core/auth.py` (BUG-1)
- [ ] Fix module import typo in `ui/reports_tab.py` (BUG-2)
- [ ] Add `import os` to `ui/reports_tab.py` (BUG-3)
- [ ] Define `APP_DIR` in `core/reports_generator.py` (BUG-4)
- [ ] Fix backslash-in-f-string SyntaxError in `ui/dialogs.py` (BUG-5)
- [ ] Implement `CsvMappingDialog` in `ui/dialogs.py` (BUG-6)
- [ ] Define `APP_DIR` in `ui/collection_tab.py` or switch to `ui/collections.py` (BUG-7)
- [ ] Fix CSV export Ellipsis bug in `ui/collection_tab.py` (BUG-8)

### Phase 1: Logic Errors
- [ ] Fix `update_card` dead code for defects field (BUG-9)
- [ ] Implement report PDF body content (BUG-10)
- [ ] Fix zero-quantity in CSV import (BUG-11)
- [ ] Remove duplicate `CollectionTab` (BUG-12)
- [ ] Implement `_setup_menu` (BUG-13)
- [ ] Implement `_show_help` with real shortcut table (BUG-14)

### Phase 2: Critical Security (Before Production)
- [ ] Fix password storage (#2)
- [ ] Add input validation (#4)

### Phase 3: High (Before Release)
- [ ] Replace bare exception handlers (#5)
- [ ] Add logging framework (#13)
- [ ] Pin dependency versions (#14)
- [ ] Add rate limiting to web scraping (#7)
- [ ] Move re-value to background thread (#17)

### Phase 4: Medium (Soon After)
- [ ] Validate scan file paths (#11)
- [ ] Add Tesseract validation (#6)
- [ ] Review thread safety (#12)
- [ ] Add user error messages (#15)
- [ ] Encrypt TOTP secret (#25)

### Phase 5: Nice to Have
- [ ] Add unit tests (#22)
- [ ] Code signing (#23)
- [ ] Windows Hello fallback (#21)
- [ ] Fix duplicate tab emoji (#18)

---

## 📝 **Notes**

- This review was updated on 2026-05-17 with all newly discovered runtime bugs
- Phase 0 bugs will prevent the app from launching at all on Python 3.11
- The `ui/dialogs.py` SyntaxError (BUG-5) cascades: it breaks `main_window.py` AND `batch_tab.py` imports
- `ui/collections.py` is the correct/complete `CollectionTab` — prefer it over `ui/collection_tab.py`
- Test thoroughly after each fix, especially authentication and database operations
- Consider adding pre-commit hooks for security linting (bandit, semgrep)

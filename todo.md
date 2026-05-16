# Trading Card Manager - Code Review TODO

**Repository:** https://github.com/doghigh/CardTCGApp

---

## 🔴 **Critical Issues**

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

### 3. Weak Recovery Codes (`core/auth.py:92`)
- **Issue:** Using `random.randint()` instead of `secrets` for cryptographic codes
- **Location:** `core/auth.py`, `generate_recovery_codes()` method
- **Current Code:**
```python
codes = [f"{random.randint(100000, 999999)}-{random.randint(1000, 9999)}" for _ in range(8)]
```
- **Fix:** Use `secrets` module
```python
codes = [f"{secrets.randbelow(1000000):06d}-{secrets.randbelow(10000):04d}" for _ in range(8)]
```
- **Priority:** CRITICAL - Cryptographic weakness

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
  - `main.py:34` - `print(f"🚀 {APP_NAME} v{APP_VERSION}...")`
  - `core/auth.py:146` - `print(f"Windows Hello error...")`
  - `core/identifier.py:70` - `print(f"OCR Error...")`
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
logger.info(f"🚀 {APP_NAME} v{APP_VERSION} started successfully!")
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

---

## 🔵 **Low Priority Issues**

### 17. Unused Imports
- **Location:** `core/identifier.py:4` - `import os` defined but not used directly
- **Fix:** Clean up or remove
- **Priority:** LOW - Code cleanliness

### 18. Windows Hello Auth Has No Fallback (`core/auth.py:121-146`)
- **Issue:** If Windows Hello fails, app could become inaccessible
- **Location:** `core/auth.py`, `request_biometric_login()`
- **Fix:** Ensure password fallback always works
- **Priority:** LOW - UX consideration

### 19. Missing Unit Tests
- **Issue:** No test coverage for security-critical functions
- **Examples:** Password verification, SQL queries, data validation
- **Priority:** LOW - Best practice

### 20. No Code Signing for Executable
- **Issue:** Distributed .exe should be signed for distribution
- **Location:** `build_exe.bat`
- **Priority:** LOW - Distribution security

---

## ✅ **Strengths to Maintain**

- ✅ Uses `secrets` module for salt generation
- ✅ PBKDF2 with 600,000 iterations (good key derivation)
- ✅ Parameterized SQL queries (mostly correct)
- ✅ Foreign key constraints enabled
- ✅ Thread-safe database with locks
- ✅ Privacy-first design (local SQLite, no cloud)

---

## 📋 **Implementation Priority**

### Phase 1: Critical (Before Production)
- [ ] Fix password storage (#2)
- [ ] Implement column whitelist (#1)
- [ ] Replace `random` with `secrets` (#3)
- [ ] Add input validation (#4)

### Phase 2: High (Before Release)
- [ ] Replace bare exception handlers (#5)
- [ ] Add logging framework (#13)
- [ ] Pin dependency versions (#14)
- [ ] Add rate limiting to web scraping (#7)

### Phase 3: Medium (Soon After)
- [ ] Validate scan file paths (#11)
- [ ] Add Tesseract validation (#6)
- [ ] Review thread safety (#12)
- [ ] Add user error messages (#15)

### Phase 4: Nice to Have
- [ ] Add unit tests (#19)
- [ ] Code signing (#20)
- [ ] Windows Hello fallback (#18)

---

## 📝 **Notes**

- This review was conducted on commit `9995c56`
- All file paths and line numbers are accurate as of that commit
- Test thoroughly after each fix, especially authentication and database operations
- Consider adding pre-commit hooks for security linting (bandit, semgrep)

# Trading Card Manager - Code Review TODO

**Repository:** https://github.com/doghigh/CardTCGApp  
**Last reviewed:** 2026-05-20

---

## ✅ **Fixed This Session** *(app now launches cleanly)*

| # | Fix | File |
|---|-----|------|
| BUG-1 | `LoginDialog` was missing — added to `core/auth.py` | `core/auth.py` |
| BUG-2 | Wrong module name `core.report_generator` → `core.reports_generator` | `ui/reports_tab.py` |
| BUG-3 | Missing `import os` (used for `os.startfile`) | `ui/reports_tab.py` |
| BUG-4 | `APP_DIR` undefined — added definition | `core/reports_generator.py` |
| BUG-5 | Backslash in f-string `{}` — SyntaxError on Python 3.11 | `ui/dialogs.py` |
| BUG-6 | `CsvMappingDialog` was missing — implemented | `ui/dialogs.py` |
| BUG-7 | `APP_DIR` undefined in export method | `ui/collection_tab.py` |
| BUG-8 | `...` (Ellipsis) written to CSV instead of row data | `ui/collection_tab.py` |
| BUG-10 | Report PDF body was a comment stub — fully implemented | `core/reports_generator.py` |
| BUG-12 | Duplicate `CollectionTab` class — `collections.py` is now dead | `ui/` |
| BUG-13 | `_setup_menu()` was empty (`pass`) — implemented | `ui/main_window.py` |
| BUG-14 | `_show_help()` showed `"..."` — now has full shortcut table | `ui/main_window.py` |
| — | `QAction` in `QtWidgets` → moved to `QtGui` (PyQt6 API change) | `ui/main_window.py` |
| — | `AuthManager` + `WindowsHelloAuth` dropped by rewrite — restored | `core/auth.py` |
| — | `ui/__init__.py` imported `LoginDialog`/`CsvMappingDialog` from wrong module | `ui/__init__.py` |
| — | `QHBoxLayout` missing from imports | `ui/dialogs.py` |
| — | `import os` missing | `ui/scan_tab.py`, `ui/batch_tab.py` |
| — | `ScanWorker` QThread class missing | `ui/scan_tab.py` |
| — | `_start_continuous_scan` wired to button but never defined | `ui/scan_tab.py` |
| — | `_save_card` and `_reset` were stub placeholders | `ui/scan_tab.py` |
| — | `card_added = pyqtSignal(int)` — wrong type, connected to `refresh()` | `ui/scan_tab.py` |
| — | Invalid format spec `:+, .2f` (space before `.2f`) | `ui/collection_tab.py` |

---

## 🔴 **Active Runtime Bugs** *(will crash specific features)*

### BUG-A. `cv2` Not Imported in `batch_tab.py` (`ui/batch_tab.py:73`)
- **Issue:** `ImageBatchWorker.run()` calls `cv2.imwrite(...)` and `cv2.cvtColor(...)` but `cv2` is never imported.
- **Error:** `NameError: name 'cv2' is not defined` — crashes every image batch import.
- **Fix:** Add `import cv2` at the top of `ui/batch_tab.py`.

### BUG-B. `ImageBatchWorker` Missing `db` Parameter (`ui/batch_tab.py:34,91`)
- **Issue:** `ImageBatchWorker.__init__` does not accept a `db` argument, yet `self.db.add_card()` is called inside `run()`. The database is never passed in.
- **Error:** `AttributeError: 'ImageBatchWorker' object has no attribute 'db'`
- **Fix:** Add `db: Database` to `__init__`, store as `self.db`, and pass `self.db` when constructing the worker in `_start_import`.

### BUG-C. `dialog.get_mapping()` Doesn't Exist (`ui/batch_tab.py:271`)
- **Issue:** `_start_import` calls `dialog.get_mapping()` after the `CsvMappingDialog` closes, but `CsvMappingDialog` has no such method — it exposes the result as `dialog.mapping`.
- **Error:** `AttributeError: 'CsvMappingDialog' object has no attribute 'get_mapping'` — crashes every CSV import.
- **Fix:** Change `dialog.get_mapping()` → `dialog.mapping`.

### BUG-D. `_inspect()` Stub — Defects Never Displayed (`ui/scan_tab.py:319`)
- **Issue:** `_inspect()` sets the grade and score labels but the defects panel (`self.defects_text`) is never populated. The line `# defects display...` is a comment stub.
- **Effect:** Defects box stays blank after every inspection.
- **Fix:**
```python
defects = self.current_inspection.get('defects', [])
if defects:
    lines = [f"• [{d['severity'].upper()}] {d['type'].replace('_', ' ').title()} @ {d['location']}"
             for d in defects]
    self.defects_text.setPlainText("\n".join(lines))
else:
    self.defects_text.setPlainText("None detected.")
```

### BUG-E. Dead `QThread()` Object in `_fetch_value` (`ui/scan_tab.py:339`)
- **Issue:** `self._val_worker = QThread()` creates an unused bare `QThread` that is immediately overwritten by `self._val_worker = w` three lines later. The bare `QThread` is never started, connected, or used.
- **Effect:** Minor memory waste; no crash, but confusing.
- **Fix:** Remove `self._val_worker = QThread()` (line 339).

### BUG-F. `QInputDialog` Imported After Its Use (`core/auth.py:99`)
- **Issue:** `from PyQt6.QtWidgets import QInputDialog` is placed at line 99, after the `LoginDialog` class that uses it in `_recovery_login`. While this works at runtime (module-level code runs before any method is called), it is unconventional and will silently break if the method is ever called before the module finishes loading (e.g., in circular import scenarios).
- **Fix:** Move the `QInputDialog` import to the top-level import block at lines 19–20.

---

## 🟡 **Logic / UX Issues**

### BUG-9. `update_card` Defects Branch Is Unreachable (`core/database.py:112`)
- **Issue:** The `if k == 'defects':` branch is filtered out before it's reached because `'defects'` is not in the `allowed` set. Defect data can never be updated via `update_card`.
- **Fix:** Add `'defects'` to the `allowed` set in `update_card`.

### BUG-G. Duplicate Tab Emoji (`ui/main_window.py:76-77`)
- **Issue:** Both "Batch Import" and "Collection" tabs use the `📦` emoji, making them visually identical in the tab bar.
- **Fix:** Change one, e.g. `"📋 Collection"`.

### BUG-H. `_revalue_worker` Blocks the UI Thread (`ui/collection_tab.py:165`)
- **Issue:** Fetches web prices for every selected card synchronously on the main thread via `QTimer.singleShot`, freezing the UI until all requests complete.
- **Fix:** Move the loop into a `QThread` worker, same pattern as `ScanWorker`.

---

## 🟠 **Security Issues** *(pre-existing)*

### SEC-1. Insecure Password Storage — **PARTIALLY FIXED** (`core/auth.py:129-134`)
- The password is now hashed with SHA256 before storage (improvement over raw key).
- However, this breaks existing `.auth.key` files written by the old code (raw bytes vs. hex string). Users who set a password before this fix will be locked out.
- **Fix:** Add a migration check: if the stored value is 32 bytes (old format), re-prompt and re-hash.

### SEC-2. Bare Exception Handlers (Multiple Files)
- `core/auth.py:146` — swallows all exceptions in `check_password`
- `core/valuator.py:38, 71, 96, 111` — swallows all in price fetchers
- `core/identifier.py:70` — swallows OCR errors
- `core/scanner.py:51` — bare `except:` in `_auto_rotate`
- **Fix:** Catch specific exception types and log them.

### SEC-3. No Input Validation Before Database INSERT (`core/database.py:73`)
- Card name, year, and price fields are stored with no type or range checks.
- **Fix:** Validate before INSERT (see previous todo.md for code example).

### SEC-4. Missing Rate Limiting in Web Scraping (`core/valuator.py`)
- No retry logic, backoff, or rate limiting — risks IP bans from TCGPlayer/eBay.
- **Fix:** Add `HTTPAdapter` with `Retry` strategy.

### SEC-5. TOTP Secret Stored in Plaintext (`core/auth.py:154`)
- `.totp_secret` file is unencrypted on disk.
- **Fix:** Encrypt with the derived key.

---

## 🔵 **Low Priority / Polish**

| # | Issue | Location |
|---|-------|----------|
| P-1 | No logging framework — uses `print()` everywhere | Multiple files |
| P-2 | Dependency versions not pinned in `requirements.txt` | `requirements.txt` |
| P-3 | Missing user-facing error messages for network/OCR failures | Multiple UI files |
| P-4 | Windows Hello auth has no password fallback guarantee | `core/auth.py` |
| P-5 | No unit tests for auth, database, or valuation logic | — |
| P-6 | File comment in `core/reports_generator.py` says wrong filename | Line 1 |
| P-7 | `ui/collections.py` is dead code — `CollectionTab` is now in `collection_tab.py` | `ui/collections.py` |
| P-8 | `base64` imported in `core/auth.py` but never used | `core/auth.py:8` |

---

## ✅ **Strengths**

- ✅ App launches and closes cleanly (no startup crashes)
- ✅ All imports resolve correctly
- ✅ Password now hashed with SHA256 before storage
- ✅ PBKDF2 with 600,000 iterations
- ✅ Parameterized SQL queries throughout
- ✅ Column whitelist in `update_card` prevents SQL injection
- ✅ Foreign key constraints enabled
- ✅ Thread-safe database with locks
- ✅ `CsvMappingDialog` implemented and functional
- ✅ Report PDF fully implemented with summary, top cards, condition distribution
- ✅ Menu bar and keyboard shortcuts fully implemented

---

## 📋 **Next Steps Priority Order**

### Immediate (crashes on use)
- [ ] Add `import cv2` to `batch_tab.py` (BUG-A)
- [ ] Pass `db` to `ImageBatchWorker` (BUG-B)
- [ ] Fix `dialog.get_mapping()` → `dialog.mapping` (BUG-C)
- [ ] Fill in defects display in `_inspect()` (BUG-D)

### Soon
- [ ] Remove dead `QThread()` line in `_fetch_value` (BUG-E)
- [ ] Move `QInputDialog` import to top of file (BUG-F)
- [ ] Fix unreachable defects branch in `update_card` (BUG-9)
- [ ] Fix duplicate tab emoji (BUG-G)
- [ ] Add migration check for old password format (SEC-1)

### Before Release
- [ ] Replace bare exception handlers (SEC-2)
- [ ] Add input validation on database INSERT (SEC-3)
- [ ] Add rate limiting to web scrapers (SEC-4)
- [ ] Move re-value to background thread (BUG-H)
- [ ] Delete dead `ui/collections.py` (P-7)

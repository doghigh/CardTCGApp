# Building & Packaging — Lorebox

## 1. Standalone executable (PyInstaller) — DONE

Produces a self-contained `dist/Lorebox/` folder (onedir) that runs
without a Python install.

```powershell
pip install pyinstaller
pyinstaller Lorebox.spec --noconfirm
```

Output: `dist/Lorebox/Lorebox.exe` (~290 MB folder).

Notes:
- The spec excludes unused heavy libs (paddleocr/paddlepaddle, matplotlib,
  pandas, scipy, …) to keep the build lean.
- `CONSOLE = False` in the spec → windowed app. Flip to `True` temporarily if
  you need a live console while debugging; diagnostics otherwise go to
  `%APPDATA%\Lorebox\logs\app.log`.
- If a rebuild fails with *Access is denied*, an instance is still running —
  close the app (or `Get-Process Lorebox | Stop-Process -Force`).

### External dependencies (not bundled)
- **Tesseract OCR** — optional. Only used as an OCR fallback; the primary path
  is the Claude vision API, so the app runs fine without it.
- **TWAIN scanner driver** — provided by the user's scanner; loaded at runtime.

## 2. App icon — DONE (placeholder)

`assets/generate_assets.py` renders the icon set (card-stack glyph on an indigo
tile). Re-run after swapping branding:

```powershell
python assets/generate_assets.py
```

Produces `icon.ico` (embedded in the exe via the spec) plus the MSIX tiles
(Square44/71/150/310, Wide310x150, StoreLogo). Replace these PNGs with real
branding later — keep the filenames.

## 3. MSIX package (Microsoft Store) — scaffolded

Manifest: `packaging/AppxManifest.xml` (fill in the Partner Center
Identity/Publisher placeholders first). Pack with:

```powershell
pyinstaller Lorebox.spec --noconfirm      # build the exe
powershell -ExecutionPolicy Bypass -File packaging\build_msix.ps1
```

`build_msix.ps1` stages `dist/` + the manifest + tiles and runs `makeappx pack`
→ `packaging/Lorebox.msix`. Requires the **Windows SDK** on PATH
(`makeappx.exe`) — easiest from a *Developer Command Prompt for VS*.

Still needed before submission:
- Fill `AppxManifest.xml` Identity/Publisher from **Partner Center**.
- Signing — the Store re-signs on submission; for local sideload testing use a
  self-signed cert + `signtool`.
- Pass the **Windows App Certification Kit (WACK)**.

## 4. Pre-submission checklist
- [x] App icon set (placeholder)
- [x] MSIX manifest + pack script
- [x] Final name / branding decided — **Lorebox** (domain loreboxapp.dev)
- [x] Partner Center identity filled into the manifest (`33303JesseCatlow.Lorebox`)
- [x] Privacy policy contact email filled (`contact@loreboxapp.dev`, both
      `site/privacy.html` and the `ebay_webhook` `/privacy` page)
- [x] Screenshots (`screenshots/sc1-4.png`, trademark-free demo data)
- [x] Store description, category, age rating
- [ ] WACK pass **for this build** — re-run per release
- [ ] Upload `packaging/Lorebox.msix` to Partner Center

## 5. Releasing an update

Every Store submission needs a strictly higher `Version` than the last one, and
a version can't be reused once submitted. Bump **all three** of these together
— `main.py` is the source of truth for the version string, but it isn't
imported anywhere else, so the other two are separate, easy-to-forget edits:

- `main.py` → `APP_VERSION` (three-part, e.g. `1.3.0`)
- `packaging/AppxManifest.xml` → `Identity/@Version` (four-part; the revision
  field **must** be `0` — the Store rejects anything else)
- `ui/main_window.py` → the `setWindowTitle("Lorebox vX.Y.Z")` call in
  `MainWindow.__init__` (not imported from `main.py` — would create a
  circular import, since `main.py` imports `MainWindow` before `APP_VERSION`
  is defined in its own module)

Then rebuild and repack:

```powershell
python -m pytest tests/ -q
pyinstaller Lorebox.spec --noconfirm
powershell -ExecutionPolicy Bypass -File packaging\build_msix.ps1
```

The Store re-signs on submission, so no signing step is needed for upload —
only for local sideload testing.

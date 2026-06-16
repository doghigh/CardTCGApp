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
- [ ] Partner Center identity filled into the manifest
- [ ] Privacy policy URL live (ebay_webhook `/privacy`) + contact email filled
- [ ] Screenshots (1366×768 or 1920×1080)
- [ ] Store description, category, age rating
- [ ] WACK pass

## 3. Pre-submission checklist
- [ ] App icon set
- [ ] Privacy policy URL live (see ebay_webhook `/privacy`)
- [ ] Screenshots (1366×768 or 1920×1080)
- [ ] Store description, category (Productivity/Utilities), age rating
- [ ] WACK pass

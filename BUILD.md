# Building & Packaging — Trading Card Manager

## 1. Standalone executable (PyInstaller) — DONE

Produces a self-contained `dist/TradingCardManager/` folder (onedir) that runs
without a Python install.

```powershell
pip install pyinstaller
pyinstaller TradingCardManager.spec --noconfirm
```

Output: `dist/TradingCardManager/TradingCardManager.exe` (~290 MB folder).

Notes:
- The spec excludes unused heavy libs (paddleocr/paddlepaddle, matplotlib,
  pandas, scipy, …) to keep the build lean.
- `CONSOLE = False` in the spec → windowed app. Flip to `True` temporarily if
  you need a live console while debugging; diagnostics otherwise go to
  `%APPDATA%\TradingCardManager\logs\app.log`.
- If a rebuild fails with *Access is denied*, an instance is still running —
  close the app (or `Get-Process TradingCardManager | Stop-Process -Force`).

### External dependencies (not bundled)
- **Tesseract OCR** — optional. Only used as an OCR fallback; the primary path
  is the Claude vision API, so the app runs fine without it.
- **TWAIN scanner driver** — provided by the user's scanner; loaded at runtime.

## 2. MSIX package (Microsoft Store) — TODO

The Store requires an MSIX. Options:

1. **MSIX Packaging Tool** (GUI, simplest): point it at the built
   `TradingCardManager.exe`, capture install, set identity/icons.
2. **makeappx / manifest** (scripted): author an `AppxManifest.xml`, then
   `makeappx pack` the `dist/TradingCardManager` folder.

Still needed before submission:
- App icons (Square44x44, Square150x150, Store logo, etc.)
- `AppxManifest.xml` with Publisher identity (from Partner Center)
- Signing — the Store re-signs on submission; for sideload testing, a
  self-signed cert.
- Pass the Windows App Certification Kit (WACK).

## 3. Pre-submission checklist
- [ ] App icon set
- [ ] Privacy policy URL live (see ebay_webhook `/privacy`)
- [ ] Screenshots (1366×768 or 1920×1080)
- [ ] Store description, category (Productivity/Utilities), age rating
- [ ] WACK pass

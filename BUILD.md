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
- **Never bundle `.env`.** The project `.env` is local-only and must not ship
  inside `dist/`. `Lorebox.spec` excludes it; verify with `findstr /s /i
  "ANTHROPIC_API_KEY" dist\Lorebox\*` before packaging.
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

## 5. Releasing an update — full rebuild-and-repack cycle

Start-to-finish checklist from "code is merged" to "live in the Store."

### 5.1 Confirm the branch

```powershell
git status
git log --oneline -3
python -m pytest tests/ -q
```

Build from a clean tree with everything you intend to ship already merged —
`main` and `release/1.3.0` are kept in sync (same commit) as of this writing,
so either is a valid base. Don't build from a feature branch.

### 5.2 Bump the version — one source of truth, then mirror everywhere

Every Store submission needs a strictly higher `Version` than the last one,
and a version can't be reused once submitted. `core/version.py` is the single
source of truth; `main.py` and `ui/main_window.py` import from it. After
bumping `core/version.py`, mirror the new version in these places:

- `core/version.py` → `APP_VERSION` (single source of truth, three-part, e.g. `1.3.0`)
- `packaging/AppxManifest.xml` → `Identity/@Version` (four-part; the revision
  field **must** be `0` — the Store rejects anything else)
- `ui/main_window.py` → `setWindowTitle("Lorebox vX.Y.Z")` in `MainWindow.__init__`
  (the `_about()` dialog already uses `APP_VERSION` from `core/version.py`)
- `run.bat` → launcher banner text
- `STORE_LISTING.md` → "What's new in this version" header version

Skip this step entirely if re-packing the *same* version that was never
actually submitted (check Partner Center's Product release history first —
a version can only be reused if it never went out).

### 5.3 Rebuild the exe and repack the MSIX

```powershell
python -m pip install pyinstaller   # if this environment doesn't have it yet
python -m pytest tests/ -q
pyinstaller Lorebox.spec --noconfirm
powershell -ExecutionPolicy Bypass -File packaging\build_msix.ps1
```

`build_msix.ps1` needs the Windows SDK's `makeappx.exe` on `PATH` — easiest
from a *Developer Command Prompt for VS*, or add the SDK's install directory
manually (e.g. `$env:PATH = "<sdk-root>\App Certification Kit;" + $env:PATH`
in the same shell before running the script). Output:
`packaging/Lorebox.msix`.

If a prior MSIX is already sitting there and you want to keep it for
comparison, move it aside first — `build_msix.ps1` overwrites in place.

### 5.4 Sign for local sideload testing

The Store re-signs on submission, so **no signing is needed for the actual
upload** — this step exists only so WACK has something installed to point
at, and so you can smoke-test the real packaged app before it ships.

```powershell
# Run this in an ELEVATED PowerShell (Run as administrator) — trusting the
# test cert writes to the LocalMachine store, which requires admin.
powershell -ExecutionPolicy Bypass -File packaging\sideload_install.ps1
```

Signs `Lorebox.msix` with a self-signed cert whose subject matches the
manifest's `Publisher`, trusts that cert locally on this machine only, and
installs the package. To uninstall afterward:

```powershell
Get-AppxPackage -Name 33303JesseCatlow.Lorebox | Remove-AppxPackage
```

### 5.5 Run WACK (Windows App Certification Kit)

```powershell
"<sdk-root>\App Certification Kit\appcertui.exe"
```

`<sdk-root>` is wherever the Windows SDK is installed — on this machine it's
`D:\Windows Kits\10`; check `C:\Program Files (x86)\Windows Kits\10` or
`C:\Program Files\Windows Kits\10` first on a fresh setup. Pick the installed
Lorebox package (from 5.4) as the test target and run the Store Certification
test suite. Fix any **Error** before submitting — Errors block certification.
A **Warning** doesn't block submission; use judgment on whether it's worth
chasing before upload (see the known one below).

**Known, accepted warning — DPIAwarenessValidation.** WACK may report
`Lorebox.exe` as "not DPI Aware." Investigated 2026-08-22: the DPI-awareness
manifest (`packaging/Lorebox.exe.manifest`, embedded via `Lorebox.spec`'s
`manifest=` kwarg) was confirmed byte-correct in both the freshly-built exe
and the actual WACK-tested installed binary — pulled directly with
`mt.exe -inputresource:Lorebox.exe;#1` from the Windows SDK — and its
`dpiAwareness` value matches Microsoft's documented recognized-format table
exactly (`PerMonitorV2` as the first comma-separated item). No app code makes
a competing DPI API call. Why WACK's parser still disagrees with what
Microsoft's own `mt.exe` reads as correct is unresolved; likely candidates
are a PyInstaller-bootloader/WACK-parser interaction that doesn't show up in
`mt.exe`'s extraction. Qt6 handles real per-monitor DPI scaling correctly at
runtime regardless of this static declaration, so real users won't see
broken UI from it. Treated as safe to ship past unless it starts blocking
certification outright (which would make it an Error, not a Warning) or a
future WACK/PyInstaller update surfaces the actual cause.

### 5.6 Submit via Partner Center

Manual — needs your login, no automation possible here:

1. Go to the app's page → **Start update** (in the *Product release*
   section). This clones the previous submission as a starting point.
2. Open **Packages** → upload the new `packaging/Lorebox.msix` → remove the
   old package entry.
3. Touch **Store listing** only if the description or screenshots changed.
4. **Submit for certification** from the App overview page.

Certification typically runs a few hours to a couple of days. Consider
**Roll out update gradually** (a Partner Center option for MSIX apps, e.g.
starting at 5%) for any release that changes behavior you haven't fully
verified against real-world usage yet — it's controllable from the app's
Overview page after publishing without needing a second submission.

### Notes

- If `.venv` needs rebuilding on a fresh machine, use **Python 3.11**, not
  3.13 — `requirements.txt` pins `numpy==1.26.4`, which has no cp313 wheel;
  pip falls back to a broken source build on 3.13 and the test suite fails
  at collection.
- `packaging/*.msix`, `*.pfx`, `*.cer` are all gitignored — the sideload test
  cert and any packed MSIX never belong in source control.

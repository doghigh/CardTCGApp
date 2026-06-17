# PyInstaller spec for Lorebox
# Build:  pyinstaller Lorebox.spec --noconfirm
# Output: dist/Lorebox/   (onedir — ideal for MSIX packaging)

from PyInstaller.utils.hooks import collect_all, collect_submodules

# Toggle for debugging: True shows a console window with live output.
# Ship with False (windowed) — diagnostics go to the rotating app.log.
CONSOLE = False

datas, binaries, hiddenimports = [], [], []

# Packages that ship binaries / data and need full collection
for pkg in ("pypdfium2", "pypdfium2_raw"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception:
        pass

# anthropic SDK — make sure all submodules are picked up
hiddenimports += collect_submodules("anthropic")
# Optional/condition­ally-imported modules referenced via try/except
hiddenimports += ["twain", "pyotp", "qrcode", "cryptography"]

# Heavy or unused libraries we deliberately leave out to keep the build lean.
# (paddleocr/paddlepaddle are listed in requirements but never imported.)
excludes = [
    "paddle", "paddleocr", "paddlepaddle",
    "matplotlib", "tkinter", "PyQt5", "PySide6", "PySide2",
    "pytest", "notebook", "IPython", "scipy", "pandas", "sympy",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Lorebox",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=CONSOLE,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",
    # Per-Monitor-V2 DPI awareness (passes WACK DPIAwarenessValidation).
    manifest="packaging/Lorebox.exe.manifest",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Lorebox",
)

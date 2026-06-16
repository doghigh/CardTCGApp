# Stage the PyInstaller output + manifest + tiles, then pack an MSIX.
#
# Prereqs:
#   - Built exe:  pyinstaller Lorebox.spec --noconfirm   (-> dist/)
#   - Windows SDK on PATH (provides makeappx.exe & signtool.exe), or run from a
#     "Developer Command Prompt for VS".
#   - AppxManifest.xml placeholders filled in (Identity/Publisher from Partner Center).
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File packaging\build_msix.ps1

$ErrorActionPreference = "Stop"
$root    = Split-Path -Parent $PSScriptRoot
$dist    = Join-Path $root "dist\Lorebox"
$staging = Join-Path $root "packaging\staging"
$assets  = Join-Path $root "assets"
$out     = Join-Path $root "packaging\Lorebox.msix"

if (-not (Test-Path $dist)) {
    throw "Build first: pyinstaller Lorebox.spec --noconfirm"
}

# Fresh staging dir = copy of the app payload
if (Test-Path $staging) { Remove-Item -Recurse -Force $staging }
New-Item -ItemType Directory -Path $staging | Out-Null
Copy-Item "$dist\*" $staging -Recurse

# Manifest at the staging root
Copy-Item (Join-Path $PSScriptRoot "AppxManifest.xml") (Join-Path $staging "AppxManifest.xml")

# Tile assets
$assetDir = Join-Path $staging "Assets"
New-Item -ItemType Directory -Path $assetDir -Force | Out-Null
Get-ChildItem $assets -Filter "*Logo.png" | Copy-Item -Destination $assetDir
Copy-Item (Join-Path $assets "StoreLogo.png") $assetDir -ErrorAction SilentlyContinue

# Pack
if (Test-Path $out) { Remove-Item -Force $out }
& makeappx pack /d $staging /p $out /overwrite
Write-Host "MSIX written to $out"
Write-Host "Next: sign for sideload testing, or upload to Partner Center (Store re-signs)."

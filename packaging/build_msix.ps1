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

# Locate makeappx.exe — prefer PATH, else search the Windows Kits roots
# (the SDK doesn't add itself to PATH; pick the newest x64 build).
$makeappx = (Get-Command makeappx.exe -ErrorAction SilentlyContinue).Source
if (-not $makeappx) {
    $kitRoots = @(
        "C:\Program Files (x86)\Windows Kits\10\bin",
        "C:\Program Files\Windows Kits\10\bin",
        "D:\Windows Kits\10\bin"
    )
    $makeappx = $kitRoots |
        Where-Object { Test-Path $_ } |
        ForEach-Object { Get-ChildItem $_ -Recurse -Filter makeappx.exe -ErrorAction SilentlyContinue } |
        Where-Object { $_.FullName -match '\\x64\\' } |
        Sort-Object FullName -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $makeappx) { throw "makeappx.exe not found. Install the Windows SDK 'Windows Store Apps Tools'." }
Write-Host "Using makeappx: $makeappx"

# Pack
if (Test-Path $out) { Remove-Item -Force $out }
& $makeappx pack /d $staging /p $out /overwrite
if ($LASTEXITCODE -ne 0) { throw "makeappx failed (exit $LASTEXITCODE)" }
Write-Host "MSIX written to $out"
Write-Host "Next: sign for sideload testing, or upload to Partner Center (Store re-signs)."

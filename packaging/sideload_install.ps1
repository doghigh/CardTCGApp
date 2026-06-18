# ============================================================================
#  Sign Lorebox.msix with a local test certificate and install it for sideload
#  testing — i.e. install the REAL packaged app on this PC the way a Store
#  customer eventually will, before it's live.
#
#  This is for LOCAL TESTING ONLY. The Microsoft Store re-signs the package
#  with its own trusted certificate when it publishes; this self-signed cert is
#  never shipped and is only trusted on your own machine.
#
#  RUN IT ELEVATED:  trusting the cert writes to the LocalMachine store, which
#  requires Administrator. Right-click PowerShell -> "Run as administrator",
#  then from the repo root:
#      powershell -ExecutionPolicy Bypass -File packaging\sideload_install.ps1
#
#  To uninstall later:
#      Get-AppxPackage -Name 33303JesseCatlow.Lorebox | Remove-AppxPackage
# ============================================================================
$ErrorActionPreference = "Stop"

$msix      = Join-Path $PSScriptRoot "Lorebox.msix"
$pfx       = Join-Path $PSScriptRoot "lorebox_test.pfx"
$cer       = Join-Path $PSScriptRoot "lorebox_test.cer"
$publisher = "CN=C328C76B-1D97-4428-888E-8AFAA26FBB7B"   # MUST match AppxManifest Publisher
$pkgName   = "33303JesseCatlow.Lorebox"
$pwPlain   = "lorebox-local-test"                         # throwaway, local only

# Require admin (cert trust + clean install need it)
$admin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw "Run this in an ELEVATED PowerShell (Run as administrator)." }

if (-not (Test-Path $msix)) { throw "MSIX not found. Build it first: packaging\build_msix.ps1" }

# 1. Reuse or create a self-signed code-signing cert whose Subject == Publisher
$cert = Get-ChildItem Cert:\CurrentUser\My |
    Where-Object { $_.Subject -eq $publisher } | Select-Object -First 1
if (-not $cert) {
    Write-Host "Creating self-signed test cert ($publisher)..."
    $cert = New-SelfSignedCertificate -Type Custom -Subject $publisher `
        -KeyUsage DigitalSignature -FriendlyName "Lorebox Local Test Signing" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
}
Write-Host "Cert thumbprint: $($cert.Thumbprint)"

# 2. Export PFX (signtool needs it) and the public .cer (to trust)
$pw = ConvertTo-SecureString -String $pwPlain -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath $pfx -Password $pw | Out-Null
Export-Certificate   -Cert $cert -FilePath $cer | Out-Null

# 3. Locate signtool.exe (Windows SDK; not on PATH by default — newest x64)
$signtool = (Get-Command signtool.exe -ErrorAction SilentlyContinue).Source
if (-not $signtool) {
    $roots = @("C:\Program Files (x86)\Windows Kits\10\bin",
               "C:\Program Files\Windows Kits\10\bin",
               "D:\Windows Kits\10\bin")
    $signtool = $roots | Where-Object { Test-Path $_ } |
        ForEach-Object { Get-ChildItem $_ -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue } |
        Where-Object { $_.FullName -match '\\x64\\' } |
        Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $signtool) { throw "signtool.exe not found. Install the Windows SDK 'Signing Tools'." }
Write-Host "Using signtool: $signtool"

# 4. Sign the MSIX (SHA256)
& $signtool sign /fd SHA256 /f $pfx /p $pwPlain $msix
if ($LASTEXITCODE -ne 0) { throw "signtool failed (exit $LASTEXITCODE)" }

# 5. Trust the cert on this machine (Trusted Root + Trusted People)
Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\Root        | Out-Null
Import-Certificate -FilePath $cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople | Out-Null
Write-Host "Test cert trusted on this machine."

# 6. Remove any prior install, then install fresh
Get-AppxPackage -Name $pkgName -ErrorAction SilentlyContinue | Remove-AppxPackage -ErrorAction SilentlyContinue
Add-AppxPackage -Path $msix
Write-Host ""
Write-Host "Installed. Launch 'Lorebox' from the Start menu."
Write-Host "(For a truly clean run, also delete  `$env:APPDATA\Lorebox  to reset data.)"

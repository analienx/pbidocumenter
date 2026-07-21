# Build standalone Windows executable (no Python install required on target machine).
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\build-exe.ps1
#   or directly:  pyinstaller pbip_documenter.spec --noconfirm

# Requires pyinstaller (auto-install if missing)
try {
    pyinstaller --version | Out-Null
}
catch {
    Write-Host "[build] pyinstaller not found, installing..."
    python -m pip install pyinstaller
}

$spec = "pbip_documenter.spec"
$outputPath = "dist\pbip_documenter.exe"

Write-Host "[build] Starting PyInstaller single-file build..."
pyinstaller --noconfirm $spec

# Determine output folder
$outputDir = Split-Path $outputPath -Parent

# Create essential runtime folders that users expect next to the .exe
$reportsDest = Join-Path $outputDir "Reports"
$exportedDest = Join-Path $outputDir "Exported Documents"

if (-not (Test-Path $reportsDest)) {
    New-Item -ItemType Directory -Path $reportsDest -Force | Out-Null
    Write-Host "[build] Created Reports folder -> $reportsDest"
}
else {
    Write-Host "[build] Reports folder already exists -> $reportsDest"
}

if (-not (Test-Path $exportedDest)) {
    New-Item -ItemType Directory -Path $exportedDest -Force | Out-Null
    Write-Host "[build] Created Exported Documents folder -> $exportedDest"
}
else {
    Write-Host "[build] Exported Documents folder already exists -> $exportedDest"
}

# Copy Full Mode batch helper into output dir under a descriptive name
$batchSource = "scripts\Run Full Mode.bat"
$batchDest = Join-Path $outputDir "PBIP Documenter - Full Mode.bat"
if (Test-Path $batchSource) {
    Copy-Item $batchSource $batchDest -Force
    Write-Host "[build] Copied PBIP Documenter - Full Mode.bat -> $batchDest"
}
else {
    Write-Host "[build] Warning: $batchSource not found, skipping copy."
}

# Remove any stale pre-built .lnk that may have been created by earlier builds
$staleLnk = Join-Path $outputDir "PBIP Documenter (Full Mode).lnk"
if (Test-Path $staleLnk) {
    Remove-Item $staleLnk -Force
    Write-Host "[build] Removed stale pre-built .lnk -> $staleLnk"
}

Write-Host "[build] Build complete."
Write-Host ""
Write-Host "Output:  $outputPath"
Write-Host ""
Write-Host "Usage:"
Write-Host "  1. Create a folder next to the .exe:"
Write-Host "       My_Documenter\"
Write-Host "       ├── pbip_documenter.exe"
Write-Host "       ├── Reports\               ← put your PBIP projects here"
Write-Host "       └── Exported Documents\     ← generated .docx files appear here"
Write-Host ""
Write-Host "  2. Double-click pbip_documenter.exe for concise mode."
Write-Host "  3. Or run the helper for full mode:"
Write-Host "       PBIP Documenter - Full Mode.bat"
Write-Host ""
Write-Host "Full-mode helper (included in build output):"
Write-Host "   PBIP Documenter - Full Mode.bat    ← run in full mode"

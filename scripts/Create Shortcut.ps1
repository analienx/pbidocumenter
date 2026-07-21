# Creates a Windows shortcut (.lnk) that runs pbip_documenter.exe in FULL mode
# Place this in the same folder as pbip_documenter.exe, then right-click → Run with PowerShell

$exeDir = $PSScriptRoot
$exePath = Join-Path $exeDir "pbip_documenter.exe"
$shortcutPath = Join-Path $exeDir "PBIP Documenter (Full Mode).lnk"

if (-not (Test-Path $exePath)) {
    Write-Host "ERROR: pbip_documenter.exe not found in this folder." -ForegroundColor Red
    Write-Host "Place this script next to pbip_documenter.exe and run it again."
    Read-Host "Press Enter to exit"
    exit 1
}

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
# Use cmd.exe as a stable anchor so the link remains valid after moving the folder
$Shortcut.TargetPath = "$env:SystemRoot\System32\cmd.exe"
$Shortcut.Arguments = '/c start "" "pbip_documenter.exe" --mode full'
$Shortcut.WorkingDirectory = $exeDir
$Shortcut.IconLocation = $exePath + ",0"
$Shortcut.Description = "PBIP Documenter - Full Mode"
$Shortcut.Save()

Write-Host "Shortcut created: $shortcutPath" -ForegroundColor Green
Write-Host "Double-click it to run the documenter in FULL mode."
Read-Host "Press Enter to exit"

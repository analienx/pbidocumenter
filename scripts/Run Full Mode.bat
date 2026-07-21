@echo off
REM Run PBIP Documenter in FULL mode
REM Place this batch file next to pbip_documenter.exe

echo Starting PBIP Documenter in FULL mode...
echo.
pbip_documenter.exe --mode full

echo.
echo Press any key to exit...
pause >nul

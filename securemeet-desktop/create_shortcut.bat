@echo off
echo ========================================
echo    SecureMeet - Create Desktop Shortcut
echo ========================================
echo.

cd /d "%~dp0"

REM Step 1: Generate icon if it doesn't exist
if not exist "assets\securemeet.ico" (
    echo [1/2] Generating app icon...
    call venv\Scripts\activate
    python create_icon.py
    if errorlevel 1 (
        echo WARNING: Could not generate icon. Shortcut will use default icon.
    )
) else (
    echo [1/2] Icon already exists.
)

REM Step 2: Create desktop shortcut using PowerShell
REM Uses Shell.Application to find the real Desktop path (works with OneDrive sync)
echo [2/2] Creating desktop shortcut...

set "SCRIPT_DIR=%~dp0"

powershell -NoProfile -Command ^
  "$desktop = [Environment]::GetFolderPath('Desktop'); " ^
  "Write-Host \"Desktop folder: $desktop\"; " ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$shortcut = $ws.CreateShortcut(\"$desktop\SecureMeet.lnk\"); " ^
  "$shortcut.TargetPath = '%SCRIPT_DIR%launch.pyw'; " ^
  "$shortcut.WorkingDirectory = '%SCRIPT_DIR%'; " ^
  "$shortcut.Description = 'SecureMeet - Privacy-first meeting minutes'; " ^
  "$ico = '%SCRIPT_DIR%assets\securemeet.ico'; " ^
  "if (Test-Path $ico) { $shortcut.IconLocation = $ico }; " ^
  "$shortcut.Save(); " ^
  "Write-Host 'Shortcut created successfully!'"

if errorlevel 1 (
    echo ERROR: Failed to create shortcut.
    pause
    exit /b 1
)

echo.
echo ========================================
echo    Done! SecureMeet shortcut is on
echo    your Desktop. Double-click to launch.
echo ========================================
echo.
pause

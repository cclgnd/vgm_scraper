@echo off
setlocal

cd /d "%~dp0"
set "APP_DIR=%~dp0"
set "PACKAGE_PARENT=%~dp0.."

where python >nul 2>nul
if errorlevel 1 (
    echo Python not found in PATH.
    echo Install Python or open this from configured dev terminal.
    echo.
    pause
    exit /b 1
)

echo Starting hidden scraper backend if needed...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$base='http://127.0.0.1:8765';" ^
  "$up=$false;" ^
  "try { Invoke-RestMethod -Uri ($base + '/api/stats') -TimeoutSec 1 | Out-Null; $up=$true } catch {}" ^
  "if (-not $up) { Start-Process -WindowStyle Hidden -WorkingDirectory '%PACKAGE_PARENT%' -FilePath 'python' -ArgumentList @('-m','vgm_scraper','api-start') }" ^
  "for ($i=0; $i -lt 25; $i++) { try { Invoke-RestMethod -Uri ($base + '/api/stats') -TimeoutSec 1 | Out-Null; exit 0 } catch { Start-Sleep -Milliseconds 250 } }" ^
  "exit 1"

if errorlevel 1 (
    echo Backend did not respond at http://127.0.0.1:8765.
    echo.
    pause
    exit /b 1
)

echo Starting Chiptune Palace...
python "%APP_DIR%player_ui\run.py"

if errorlevel 1 (
    echo.
    echo Player UI exited with an error.
    echo.
    pause
)

endlocal

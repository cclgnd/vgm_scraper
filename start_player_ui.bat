@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python not found in PATH.
    echo Install Python or open this from configured dev terminal.
    echo.
    pause
    exit /b 1
)

echo Starting Chiptune Palace...
python player_ui\run.py

if errorlevel 1 (
    echo.
    echo Player UI exited with an error.
    echo.
    pause
)

endlocal

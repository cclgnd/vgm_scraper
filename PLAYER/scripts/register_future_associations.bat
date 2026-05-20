@echo off
setlocal EnableExtensions

set "APP_DIR=%~dp0.."
for %%I in ("%APP_DIR%") do set "APP_DIR=%%~fI"
set "RUNNER=%APP_DIR%\run_simpleplayer.bat"
set "PROGID=SIMPLEPLAYER.FutureChiptune"

if /I "%~1"=="uninstall" goto uninstall
if /I "%~1"=="remove" goto uninstall

echo Registering SIMPLEPLAYER future-format file associations for the current user...
echo App: "%RUNNER%"

reg add "HKCU\Software\Classes\%PROGID%" /ve /d "SIMPLEPLAYER future chiptune file" /f >nul
reg add "HKCU\Software\Classes\%PROGID%\DefaultIcon" /ve /d "\"%RUNNER%\",0" /f >nul
reg add "HKCU\Software\Classes\%PROGID%\shell\open\command" /ve /d "\"%RUNNER%\" \"%%1\"" /f >nul

for %%E in (
  .psf2 .minipsf2
  .usf .miniusf
  .gsf .minigsf
  .2sf .mini2sf
  .ssf .minissf
  .dsf .minidsf
  .qsf .miniqsf
  .hoot .m1 .xml
) do (
  reg add "HKCU\Software\Classes\%%E" /ve /d "%PROGID%" /f >nul
)

echo.
echo Done. Explorer can now open these with SIMPLEPLAYER:
echo .psf2 .minipsf2 .usf .miniusf .gsf .minigsf .2sf .mini2sf .ssf .minissf .dsf .minidsf .qsf .miniqsf .hoot .m1 .xml
echo.
echo Note: only formats with an implemented backend will actually play.
echo Others will open the player and report "backend not installed yet."
echo.
echo If Explorer does not refresh immediately, log out/in or restart Explorer.
echo To remove these associations, run:
echo "%~f0" uninstall
exit /b 0

:uninstall
echo Removing SIMPLEPLAYER future-format file associations for the current user...
for %%E in (
  .psf2 .minipsf2
  .usf .miniusf
  .gsf .minigsf
  .2sf .mini2sf
  .ssf .minissf
  .dsf .minidsf
  .qsf .miniqsf
  .hoot .m1 .xml
) do (
  reg delete "HKCU\Software\Classes\%%E" /ve /f >nul 2>nul
)
reg delete "HKCU\Software\Classes\%PROGID%" /f >nul 2>nul
echo Done.
exit /b 0

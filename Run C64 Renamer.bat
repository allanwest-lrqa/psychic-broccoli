@echo off
rem Double-click launcher for running C64 Renamer from source on Windows.
rem (Requires Python 3 installed. If you have the standalone c64renamer.exe you
rem  do not need this file or Python at all -- just run the .exe.)

cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0c64renamer_app.py"
    exit /b
)

where py >nul 2>nul
if %errorlevel%==0 (
    start "" py -w "%~dp0c64renamer_app.py"
    exit /b
)

echo Python 3 was not found on this PC.
echo Install it from https://www.python.org/downloads/ (tick "Add to PATH"),
echo or use the standalone c64renamer.exe which needs no Python.
pause

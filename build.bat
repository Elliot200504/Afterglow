@echo off
rem builds dist\Afterglow\Afterglow.exe (run run.bat once first so .venv exists)
cd /d "%~dp0"

.venv\Scripts\pip install pyinstaller
.venv\Scripts\pyinstaller --noconfirm --windowed --name Afterglow --icon assets\afterglow.ico ^
    --add-data "ui;ui" --add-data "assets;assets" ^
    --collect-all winrt --collect-all webview --hidden-import pystray._win32 ^
    afterglow_app.py

echo.
echo Done: dist\Afterglow\Afterglow.exe
pause

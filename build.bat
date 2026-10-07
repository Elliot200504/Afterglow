@echo off
rem builds dist\SpotLight\SpotLight.exe (run run.bat once first so .venv exists)
cd /d "%~dp0"

.venv\Scripts\pip install pyinstaller
.venv\Scripts\pyinstaller --noconfirm --windowed --name SpotLight --icon assets\spotlight.ico ^
    --add-data "ui;ui" --add-data "assets;assets" ^
    --collect-all winrt --collect-all webview --hidden-import pystray._win32 ^
    spotlight_app.py

echo.
echo Done: dist\SpotLight\SpotLight.exe
pause

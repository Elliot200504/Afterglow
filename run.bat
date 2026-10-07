@echo off
cd /d "%~dp0"

rem first time: make a virtual environment and install the packages
if not exist .venv (
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)

rem pythonw = no console window
start "" .venv\Scripts\pythonw.exe -m afterglow

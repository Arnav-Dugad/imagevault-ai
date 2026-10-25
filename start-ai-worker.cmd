@echo off
rem Starts the ImageVault laptop AI worker as an icon next to the clock (right-click it for Start/Stop).
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" -m app.tray

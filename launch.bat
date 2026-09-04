@echo off
chcp 65001 >nul
setlocal

set "PY=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%PY%" set "PY=pythonw"

start "" "%PY%" "%~dp0main.py"

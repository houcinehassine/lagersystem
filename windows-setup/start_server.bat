@echo off
REM Wird von der Windows-Aufgabenplanung automatisch gestartet (siehe Anleitung).
REM Nicht direkt per Doppelklick aufrufen - dafuer gibt es start.bat.
cd /d "%~dp0"

venv\Scripts\python.exe backup.py >> lagersystem.log 2>&1
venv\Scripts\streamlit.exe run app.py --server.headless true >> lagersystem.log 2>&1

@echo off
REM Manueller Fallback - per Doppelklick. Prueft ob der Hintergrunddienst schon
REM laeuft (dann nur Browser oeffnen), sonst wird die App direkt gestartet.
cd /d "%~dp0"

netstat -ano | findstr ":8501" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo Die App laeuft bereits im Hintergrund - oeffne den Browser...
    start http://localhost:8501
) else (
    venv\Scripts\python.exe backup.py
    venv\Scripts\streamlit.exe run app.py
)

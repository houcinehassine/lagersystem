#!/bin/bash
# Wird vom Hintergrunddienst (LaunchAgent) beim Login automatisch gestartet
# und bei einem Absturz automatisch neu gestartet. Nicht per Doppelklick
# aufrufen - dafuer gibt es start.command.
set -euo pipefail
cd "$(dirname "$0")"

./backup.sh
source venv/bin/activate
exec streamlit run app.py --server.headless true

cd "$(dirname "$0")"

if lsof -i :8501 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Die App laeuft bereits im Hintergrund - oeffne den Browser..."
    open "http://localhost:8501"
else
    ./backup.sh
    source venv/bin/activate
    streamlit run app.py
fi

#!/bin/bash
# Sicherheitskopie der Lagerdatenbank - wird bei jedem Start der App automatisch
# ausgefuehrt (siehe start.command / server.sh). Ein Backup pro Tag genuegt,
# deshalb ueberschreibt ein zweiter Start am selben Tag die Datei von heute.
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p backups
datum=$(date +%Y-%m-%d)
rm -f "backups/lager_${datum}.db" "backups/lager_${datum}.db-wal" "backups/lager_${datum}.db-shm"
sqlite3 lager.db "VACUUM INTO 'backups/lager_${datum}.db'"

# Nur die letzten 30 Tage aufheben, aeltere Backups aufraeumen
ls -1t backups/lager_*.db 2>/dev/null | tail -n +31 | while IFS= read -r datei; do
    rm -f -- "$datei"
done

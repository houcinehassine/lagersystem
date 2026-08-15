"""Taegliche Sicherheitskopie der Lagerdatenbank - plattformunabhaengig (Mac/Windows).
Wird bei jedem Start der App automatisch ausgefuehrt (siehe start_server.bat / start.bat).
Ein Backup pro Tag genuegt, ein zweiter Start am selben Tag ueberschreibt die heutige Datei.
"""
import datetime as dt
import sqlite3
from pathlib import Path

BASIS = Path(__file__).resolve().parent
DB = BASIS / "lager.db"
BACKUPS = BASIS / "backups"


def sichern() -> None:
    BACKUPS.mkdir(exist_ok=True)
    datum = dt.date.today().isoformat()
    ziel = BACKUPS / f"lager_{datum}.db"
    for pfad in (ziel, ziel.with_suffix(".db-wal"), ziel.with_suffix(".db-shm")):
        pfad.unlink(missing_ok=True)

    conn = sqlite3.connect(DB)
    try:
        conn.execute(f"VACUUM INTO '{ziel.as_posix()}'")
    finally:
        conn.close()

    # Nur die letzten 30 Tage aufheben, aeltere Backups aufraeumen
    alle_backups = sorted(BACKUPS.glob("lager_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for alt in alle_backups[30:]:
        alt.unlink(missing_ok=True)


if __name__ == "__main__":
    sichern()
    print("Backup erstellt.")

"""Einmaliges Migrations-Script: kopiert alle Daten aus der lokalen SQLite-
Datenbank (lager.db) in eine Postgres-Datenbank (z.B. Neon).

Nutzung:
    export DATABASE_URL="postgresql://...neon.tech/..."
    venv/bin/python migrate_sqlite_to_postgres.py

Kann gefahrlos mehrfach ausgefuehrt werden - leert vor jeder Tabelle die
Zieltabelle, bevor die aktuellen Daten aus SQLite eingespielt werden.
"""
from __future__ import annotations

import os
import sqlite3
import sys

import psycopg2

TABELLEN = [
    "Lager", "Typ", "Einheit", "Konfiguration", "Profil_Abk", "Material_Gruppe",
    "Artikel_Gruppe", "Artikel_Liste", "Reste", "Papierkorb", "Verlauf",
]

# Tabellen mit SERIAL-Primaerschluessel - nach dem Kopieren muss die Postgres-
# interne Sequenz auf den hoechsten uebertragenen Wert gesetzt werden, sonst
# kollidiert der naechste automatisch vergebene Wert mit einer bestehenden ID.
SERIAL_PKS = {
    "Lager": "LagerID",
    "Typ": "TypID",
    "Einheit": "EinheitID",
    "Artikel_Liste": "ID",
    "Reste": "ID",
    "Papierkorb": "ID",
    "Verlauf": "ID",
}


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Fehler: DATABASE_URL ist nicht gesetzt. Siehe Kommentar oben im Script.")
        sys.exit(1)

    # Zielschema anlegen, falls noch nicht vorhanden (nutzt automatisch Postgres,
    # da DATABASE_URL gesetzt ist).
    import db as ziel_db
    ziel_db.init_db()

    quelle = sqlite3.connect("lager.db")
    quelle.row_factory = sqlite3.Row

    ziel_conn = psycopg2.connect(database_url)
    try:
        cur = ziel_conn.cursor()
        for tabelle in TABELLEN:
            zeilen = quelle.execute(f"SELECT * FROM {tabelle}").fetchall()
            cur.execute(f"DELETE FROM {tabelle}")
            if not zeilen:
                print(f"{tabelle}: keine Zeilen in SQLite, Zieltabelle bleibt leer.")
                continue

            spalten = zeilen[0].keys()
            spalten_liste = ", ".join(spalten)
            platzhalter = ", ".join(["%s"] * len(spalten))
            for zeile in zeilen:
                werte = [zeile[s] for s in spalten]
                cur.execute(
                    f"INSERT INTO {tabelle} ({spalten_liste}) VALUES ({platzhalter})", werte
                )

            if tabelle in SERIAL_PKS:
                pk = SERIAL_PKS[tabelle]
                # pg_get_serial_sequence() erwartet Tabellen-/Spaltennamen als
                # Text-Literal (keine SQL-Bezeichner) - Postgres speichert
                # unquotierte Namen intern klein, deshalb hier explizit .lower().
                cur.execute(
                    f"SELECT setval(pg_get_serial_sequence('{tabelle.lower()}', '{pk.lower()}'), "
                    f"COALESCE((SELECT MAX({pk}) FROM {tabelle}), 1))"
                )

            print(f"{tabelle}: {len(zeilen)} Zeilen uebertragen.")

        ziel_conn.commit()
    finally:
        ziel_conn.close()
        quelle.close()

    print("Fertig - alle Daten aus lager.db liegen jetzt auch in der Cloud-Datenbank.")


if __name__ == "__main__":
    main()

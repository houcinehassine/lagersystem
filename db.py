"""Datenzugriffsschicht fuer das Lager System.

Unterstuetzt zwei Betriebsarten, automatisch anhand der Umgebungsvariable
DATABASE_URL gewaehlt:

- Keine DATABASE_URL gesetzt (Normalfall lokal auf Mac/Windows): lokale
  SQLite-Datei (lager.db) - wie bisher, keine Aenderung am Verhalten.
- DATABASE_URL gesetzt (z.B. via Streamlit-Secrets in der Cloud, verweist
  auf eine gehostete Postgres-Datenbank wie Neon): Postgres.

Der Rest der App (logic.py, app.py) merkt davon nichts - die Funktionen
hier (fetch_all, fetch_one, fetch_df, execute, ...) verhalten sich in
beiden Faellen gleich.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import psycopg2
import psycopg2.extras

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "lager.db"
SCHEMA_PATH_SQLITE = BASE_DIR / "schema.sql"
SCHEMA_PATH_POSTGRES = BASE_DIR / "schema_postgres.sql"


def _hole_database_url() -> str | None:
    """Postgres-Verbindung fuer Cloud-Betrieb - zuerst aus Streamlit-Secrets
    (so wird sie auf Streamlit Community Cloud hinterlegt), sonst aus einer
    normalen Umgebungsvariable (praktisch zum lokalen Testen). Ist beides
    nicht gesetzt, bleibt es beim lokalen SQLite-Betrieb."""
    try:
        import streamlit as st

        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
    except Exception:
        pass
    return os.environ.get("DATABASE_URL")


DATABASE_URL = _hole_database_url()

# Sowohl psycopg2.IntegrityError als auch sqlite3.IntegrityError erfuellen die
# DB-API-2.0-Schnittstelle - Aufrufer (app.py) fangen einheitlich db.IntegrityError,
# ohne wissen zu muessen, welcher Datenbanktyp gerade aktiv ist.
IntegrityError = psycopg2.IntegrityError if DATABASE_URL else sqlite3.IntegrityError


def _ist_postgres() -> bool:
    return DATABASE_URL is not None


def _uebersetze(query: str) -> str:
    """Uebersetzt SQLite-Platzhalter (?) in Postgres-Platzhalter (%s), falls noetig."""
    return query.replace("?", "%s") if _ist_postgres() else query


def get_connection():
    if _ist_postgres():
        # Kein cursor_factory hier auf Verbindungsebene - pandas' read_sql_query
        # (siehe fetch_df) braucht einen normalen Tupel-Cursor. Fuer unsere
        # eigenen dict-artigen Zugriffe (row["Spalte"]) siehe _cursor() unten.
        return psycopg2.connect(DATABASE_URL)

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL erlaubt gleichzeitiges Lesen waehrend ein anderer Nutzer schreibt -
    # wichtig, sobald mehrere Leute im Netzwerk parallel auf die App zugreifen.
    conn.execute("PRAGMA journal_mode = WAL")
    # Bei kurzzeitig konkurrierenden Schreibzugriffen bis zu 5s warten statt
    # sofort mit "database is locked" abzubrechen.
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db() -> None:
    """Legt alle Tabellen an, falls noch nicht vorhanden, und fuellt Standardwerte."""
    conn = get_connection()
    try:
        schema_pfad = SCHEMA_PATH_POSTGRES if _ist_postgres() else SCHEMA_PATH_SQLITE
        skript = schema_pfad.read_text(encoding="utf-8")
        if _ist_postgres():
            conn.cursor().execute(skript)
        else:
            conn.executescript(skript)
        _seed_defaults(conn)
        conn.commit()
    finally:
        conn.close()


def _seed_defaults(conn) -> None:
    """Fuellt Typ/Einheit mit sinnvollen Standardwerten, falls noch leer.

    Lager/Profil_Abk/Material_Gruppe sind projektspezifisch und werden
    ueber die Einstellungen-Seite in der App gepflegt.
    """
    cur = _cursor(conn)

    cur.execute("SELECT COUNT(*) AS anzahl FROM Typ")
    if cur.fetchone()["anzahl"] == 0:
        cur.executemany(
            _uebersetze("INSERT INTO Typ (Bezeichnung) VALUES (?)"), [("Voll",), ("Rest",)]
        )

    cur.execute("SELECT COUNT(*) AS anzahl FROM Einheit")
    if cur.fetchone()["anzahl"] == 0:
        cur.executemany(
            _uebersetze("INSERT INTO Einheit (Symbol) VALUES (?)"),
            [("Stk",), ("kg",), ("m",), ("mm",)],
        )


@contextmanager
def connection():
    """Context-Manager fuer eine kurzlebige Verbindung (Commit/Close automatisch)."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------
# Postgres faltet unquotierte Bezeichner (Tabellen/Spalten) automatisch auf
# Kleinschreibung - "LaengeMM" kommt als "laengemm" zurueck. sqlite3.Row
# erlaubt Zugriff per Position (row[0]) UND per Name in der im Schema
# definierten Gross-/Kleinschreibung. _Zeile bildet das fuer Postgres nach -
# und zwar, indem die Schluessel schon beim Erstellen umbenannt werden
# (nicht erst bei row["Spalte"]), damit auch dict(row) (z.B. in
# logic.hole_daten_ag) die richtige Schreibweise behaelt.
# --------------------------------------------------------------

class _Zeile(dict):
    def __init__(self, mapping):
        self._werte = list(mapping.values())
        super().__init__(
            (_SCHEMA_SPALTEN.get(k.lower(), k), v) for k, v in mapping.items()
        )

    def __getitem__(self, schluessel):
        if isinstance(schluessel, int):
            return self._werte[schluessel]
        return super().__getitem__(schluessel)


def _normalisiere_zeile(row):
    if row is None or not _ist_postgres():
        return row
    return _Zeile(row)


def _normalisiere_df(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame-Spaltennamen fuer die Anzeige in die im Schema definierte
    Gross-/Kleinschreibung zurueckbringen (Postgres liefert sie klein)."""
    if _ist_postgres():
        df = df.rename(columns={c: _SCHEMA_SPALTEN.get(c.lower(), c) for c in df.columns})
    return df


# Fuer _normalisiere_df: nur echte Schema-Spalten umbenennen (nicht per
# Alias erzeugte Anzeigespalten wie "Quelle") - aus dem Postgres-Schema
# extrahiert, damit es garantiert mit den echten Tabellen uebereinstimmt.
def _lade_schema_spalten() -> dict[str, str]:
    import re

    text = SCHEMA_PATH_POSTGRES.read_text(encoding="utf-8")
    namen = re.findall(r"^\s*(\w+)\s+(?:TEXT|REAL|INTEGER|SERIAL)\b", text, re.MULTILINE)
    return {n.lower(): n for n in namen}


_SCHEMA_SPALTEN = _lade_schema_spalten()


def _cursor(conn):
    """Cursor mit dict-artigem Zeilenzugriff (row["Spalte"]) - bei SQLite
    automatisch ueber row_factory, bei Postgres explizit ueber RealDictCursor.
    Nicht fuer fetch_df verwenden (siehe get_connection)."""
    if _ist_postgres():
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()


# --------------------------------------------------------------
# Generische Hilfsfunktionen
# --------------------------------------------------------------

def fetch_all(query: str, params: tuple = ()) -> list:
    with connection() as conn:
        cur = _cursor(conn)
        cur.execute(_uebersetze(query), params)
        return [_normalisiere_zeile(r) for r in cur.fetchall()]


def fetch_one(query: str, params: tuple = ()):
    with connection() as conn:
        cur = _cursor(conn)
        cur.execute(_uebersetze(query), params)
        return _normalisiere_zeile(cur.fetchone())


def fetch_df(query: str, params: tuple = ()) -> pd.DataFrame:
    """Wie fetch_all, aber direkt als DataFrame - praktisch fuer Streamlit-Tabellen."""
    with connection() as conn:
        df = pd.read_sql_query(_uebersetze(query), conn, params=params)
        return _normalisiere_df(df)


def execute(query: str, params: tuple = ()) -> int:
    """Fuehrt INSERT/UPDATE/DELETE aus und gibt die Anzahl betroffener Zeilen zurueck."""
    with connection() as conn:
        cur = conn.cursor()
        cur.execute(_uebersetze(query), params)
        return cur.rowcount


def value_exists(table: str, column: str, value: str) -> bool:
    """Entspricht der alten VBA-Funktion WertExistiertInTabelle."""
    row = fetch_one(f"SELECT 1 FROM {table} WHERE {column} = ? LIMIT 1", (value,))
    return row is not None


# --------------------------------------------------------------
# Konfiguration (einstellbare Schwellenwerte etc.)
# --------------------------------------------------------------

def hole_konfiguration(schluessel: str, standard: float) -> float:
    """Liest einen konfigurierbaren Wert (z.B. 'SchrottGrenzeMM'); Standard, falls noch nicht gesetzt."""
    row = fetch_one("SELECT Wert FROM Konfiguration WHERE Schluessel = ?", (schluessel,))
    return float(row["Wert"]) if row else standard


def setze_konfiguration(schluessel: str, wert: float) -> None:
    execute(
        "INSERT INTO Konfiguration (Schluessel, Wert) VALUES (?, ?) "
        "ON CONFLICT(Schluessel) DO UPDATE SET Wert = excluded.Wert",
        (schluessel, str(wert)),
    )

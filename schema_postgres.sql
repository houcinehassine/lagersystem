-- ============================================================
-- Lager System - PostgreSQL-Datenbankschema (fuer Cloud-Betrieb,
-- z.B. Neon). Inhaltlich identisch zu schema.sql (SQLite-Version),
-- nur mit Postgres-kompatibler Syntax (SERIAL statt AUTOINCREMENT,
-- keine PRAGMA-Zeilen). Wird von db.py automatisch verwendet, sobald
-- eine DATABASE_URL (Postgres-Verbindung) konfiguriert ist.
-- ============================================================

-- --------------------------------------------------------------
-- Lookup-Tabellen (bisher im Blatt "Einstellung")
-- --------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Lager (
    LagerID     SERIAL PRIMARY KEY,
    OrtRegal    TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS Typ (
    TypID       SERIAL PRIMARY KEY,
    Bezeichnung TEXT NOT NULL UNIQUE          -- "Voll" / "Rest"
);

CREATE TABLE IF NOT EXISTS Einheit (
    EinheitID   SERIAL PRIMARY KEY,
    Symbol      TEXT NOT NULL UNIQUE          -- z.B. Stk, kg, m
);

CREATE TABLE IF NOT EXISTS Konfiguration (
    Schluessel  TEXT PRIMARY KEY,               -- z.B. "SchrottGrenzeMM"
    Wert        TEXT NOT NULL                   -- als Text gespeichert, je nach Schluessel interpretiert
);

CREATE TABLE IF NOT EXISTS Profil_Abk (
    Profil      TEXT PRIMARY KEY,             -- voller Profilname
    Abkuerzung  TEXT NOT NULL                 -- Kuerzel fuer Barcode
);

CREATE TABLE IF NOT EXISTS Material_Gruppe (
    Material    TEXT PRIMARY KEY,
    Gruppe      TEXT NOT NULL,
    Abkuerzung  TEXT NOT NULL                 -- Kuerzel fuer Barcode
);

-- --------------------------------------------------------------
-- Artikel_Gruppe (bisher Blatt "Artikel Gruppe")
-- Stammdaten je Artikeltyp, generiert den Haupt-Barcode
-- --------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Artikel_Gruppe (
    Barcode         TEXT PRIMARY KEY,         -- Haupt-Barcode, z.B. "LPAL0001"
    Bezeichnung     TEXT NOT NULL,            -- Profil-Mass-Material
    Profil          TEXT NOT NULL,
    Mass            TEXT NOT NULL,
    Material        TEXT NOT NULL
);

-- --------------------------------------------------------------
-- Artikel_Liste (volle Stuecke), Reste (< 1000mm), Verlauf (Protokoll)
-- Alle drei identisch aufgebaut (ArtikelStueck-Typ aus dem VBA-Code)
-- --------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Artikel_Liste (
    ID              SERIAL PRIMARY KEY,
    Datum           TEXT NOT NULL,
    Barcode         TEXT NOT NULL,
    Barcode2        TEXT NOT NULL UNIQUE,
    Bezeichnung     TEXT,
    Profil          TEXT,
    Mass            TEXT,
    LaengeMM        REAL,
    MaterialGruppe  TEXT,
    Material        TEXT,
    OrtRegal        TEXT,
    Typ             TEXT,                     -- "Voll" / "Rest"
    MengeStueck     INTEGER,
    EPreis          REAL,
    EPreisEinheit   TEXT,
    FOREIGN KEY (Barcode) REFERENCES Artikel_Gruppe (Barcode)
);

CREATE TABLE IF NOT EXISTS Reste (
    ID              SERIAL PRIMARY KEY,
    Datum           TEXT NOT NULL,
    Barcode         TEXT NOT NULL,
    Barcode2        TEXT NOT NULL UNIQUE,
    Bezeichnung     TEXT,
    Profil          TEXT,
    Mass            TEXT,
    LaengeMM        REAL,
    MaterialGruppe  TEXT,
    Material        TEXT,
    OrtRegal        TEXT,
    Typ             TEXT,
    MengeStueck     INTEGER,
    EPreis          REAL,
    EPreisEinheit   TEXT,
    FOREIGN KEY (Barcode) REFERENCES Artikel_Gruppe (Barcode)
);

CREATE TABLE IF NOT EXISTS Papierkorb (
    ID              SERIAL PRIMARY KEY,
    QuellTabelle    TEXT NOT NULL,            -- "Artikel_Liste" oder "Reste" - fuer die Wiederherstellung
    GeloeschtAm     TEXT NOT NULL,
    Datum           TEXT,
    Barcode         TEXT,
    Barcode2        TEXT,
    Bezeichnung     TEXT,
    Profil          TEXT,
    Mass            TEXT,
    LaengeMM        REAL,
    MaterialGruppe  TEXT,
    Material        TEXT,
    OrtRegal        TEXT,
    Typ             TEXT,
    MengeStueck     INTEGER,
    EPreis          REAL,
    EPreisEinheit   TEXT
);

CREATE TABLE IF NOT EXISTS Verlauf (
    ID              SERIAL PRIMARY KEY,
    Datum           TEXT NOT NULL,
    Barcode         TEXT NOT NULL,
    Barcode2        TEXT NOT NULL,
    Bezeichnung     TEXT,
    Profil          TEXT,
    Mass            TEXT,
    LaengeMM        REAL,                     -- negativ = Entnahme (wie im bestehenden Code)
    MaterialGruppe  TEXT,
    Material        TEXT,
    OrtRegal        TEXT,
    Typ             TEXT,                     -- "Voll" / "Rest" / "Verbrauch"
    MengeStueck     INTEGER,
    EPreis          REAL,
    EPreisEinheit   TEXT
);

-- --------------------------------------------------------------
-- Indizes fuer die Felder, die am haeufigsten durchsucht werden
-- --------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_ArtikelListe_Barcode  ON Artikel_Liste (Barcode);
CREATE INDEX IF NOT EXISTS idx_Reste_Barcode         ON Reste (Barcode);
CREATE INDEX IF NOT EXISTS idx_Verlauf_Barcode       ON Verlauf (Barcode);

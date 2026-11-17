"""Excel-Import: liest eine vorbereitete Artikelliste (.xlsx) und bucht sie ins Lager ein.

Ablauf (siehe app.py -> page_import):
1. analysiere()  - liest die Datei, erkennt die Spalten selbst, prueft jede Zeile und
                   rechnet im Trockenlauf durch, was passieren wuerde (Vorschau, schreibt nichts).
2. importiere()  - macht dasselbe, schreibt aber alles in EINER Transaktion in die
                   Datenbank: entweder landet die komplette Liste im Lager oder - bei
                   einem Fehler - gar nichts.

Was das System selbst erkennt/anlegt:
- Spalten anhand ihrer Ueberschrift (Reihenfolge egal, Gross-/Kleinschreibung egal,
  gaengige Synonyme wie "Ort"/"Regal"/"Lagerort", "Laenge"/"Laenge_mm" ...).
- Unbekannte Profile, Materialien, Lagerorte und Einheiten werden neu angelegt
  (Barcode-Kuerzel werden automatisch gebildet).
- Fehlende Artikelgruppen werden angelegt, mit demselben Barcode-Schema wie
  logic.create_artikel_gruppe (Kuerzel + laufende 4-stellige Nummer).
- Voll/Rest wird wie beim manuellen "Hinzufuegen" ueber die Schrott-/Rest-Grenze entschieden
  (Laenge <= Grenze -> Tabelle "Reste", sonst "Artikel_Liste").
- Jede Zeile bekommt einen Stueck-Barcode (Barcode2) und einen Verlauf-Eintrag,
  genau wie logic.add_artikel_stueck.
"""
from __future__ import annotations

import datetime as _dt
import io
import itertools
import math
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import openpyxl
from openpyxl.styles import Font

import db
import logic

MAX_DATENZEILEN = 5000
_MAX_GELESENE_ZEILEN = 20000  # Schutz vor Blaettern, die bis zur letzten Excel-Zeile formatiert sind


class ImportFehler(Exception):
    """Die Datei als Ganzes ist nicht verwendbar (kein Excel, Spalten fehlen, zu gross ...)."""


# --------------------------------------------------------------
# Spaltenerkennung
# --------------------------------------------------------------

# Ueberschriften werden vor dem Vergleich normalisiert (klein, ae/oe/ue/ss, nur Buchstaben/Ziffern).
_SYNONYME = {
    "profil": {"profil", "profiltyp", "profilart", "profilname", "artikelart"},
    "mass": {"mass", "masse", "abmessung", "abmessungen", "querschnitt", "dimension", "groesse"},
    "material": {"material", "werkstoff", "sorte", "stahlsorte"},
    "gruppe": {"materialgruppe", "gruppe", "werkstoffgruppe"},
    "laenge": {"laenge", "laengemm", "laengeinmm", "length"},
    "menge": {"menge", "mengestueck", "stueck", "stueckzahl", "anzahl", "stk"},
    "ort": {"lagerort", "ort", "regal", "ortregal", "lager", "standort"},
    "preis": {"epreis", "preis", "einzelpreis"},
    "einheit": {"epreiseinheit", "preiseinheit", "einheit"},
}
_PFLICHTFELDER = ("profil", "mass", "material", "laenge", "ort")
_FELDNAMEN = {
    "profil": "Profil", "mass": "Mass", "material": "Material", "laenge": "Laenge_mm", "ort": "Lagerort",
}
_FELD_NACH_KOPF = {kopf: feld for feld, koepfe in _SYNONYME.items() for kopf in koepfe}


def _norm_kopf(wert) -> str:
    s = str(wert).strip().lower()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(alt, neu)
    return re.sub(r"[^a-z0-9]", "", s)


def _leer(wert) -> bool:
    return wert is None or (isinstance(wert, str) and not wert.strip())


def _text(wert) -> str:
    if _leer(wert):
        return ""
    if isinstance(wert, float) and wert.is_integer():
        return str(int(wert))
    return str(wert).strip()


def _finde_kopfzeile(zeilen: list) -> tuple[int | None, dict[str, int]]:
    """Sucht in den ersten Zeilen die, die die meisten bekannten Spaltenueberschriften enthaelt."""
    beste_idx, beste_spalten = None, {}
    for idx, werte in enumerate(zeilen[:15]):
        spalten: dict[str, int] = {}
        for pos, wert in enumerate(werte):
            if _leer(wert):
                continue
            feld = _FELD_NACH_KOPF.get(_norm_kopf(wert))
            if feld and feld not in spalten:
                spalten[feld] = pos
        if len(spalten) > len(beste_spalten):
            beste_idx, beste_spalten = idx, spalten
    return beste_idx, beste_spalten


def _lese_blatt(daten: bytes) -> tuple[list, int, dict[str, int]]:
    try:
        arbeitsmappe = openpyxl.load_workbook(io.BytesIO(daten), data_only=True)
    except Exception:
        raise ImportFehler("Die Datei konnte nicht gelesen werden. Bitte eine Excel-Datei (.xlsx) hochladen.")

    gefunden: list[str] = []
    for blatt in arbeitsmappe.worksheets:
        zeilen = list(itertools.islice(blatt.iter_rows(values_only=True), _MAX_GELESENE_ZEILEN))
        idx, spalten = _finde_kopfzeile(zeilen)
        if idx is not None and all(f in spalten for f in _PFLICHTFELDER):
            return zeilen, idx, spalten
        if idx is not None:
            fehlend = [_FELDNAMEN[f] for f in _PFLICHTFELDER if f not in spalten]
            gefunden.append(f"Blatt '{blatt.title}': es fehlt die Spalte {', '.join(fehlend)}")

    if gefunden:
        raise ImportFehler(
            "Die Spalten wurden nicht vollstaendig erkannt. " + "; ".join(gefunden) + ". "
            "Benoetigt werden: Profil, Mass, Material, Laenge_mm, Lagerort (optional: Menge, E-Preis, "
            "E-Preis-Einheit). Am einfachsten die Vorlage herunterladen."
        )
    raise ImportFehler(
        "Keine Spaltenueberschriften erkannt. Benoetigt werden: Profil, Mass, Material, Laenge_mm, "
        "Lagerort (optional: Menge, E-Preis, E-Preis-Einheit). Am einfachsten die Vorlage herunterladen."
    )


# --------------------------------------------------------------
# Werte lesen und normalisieren
# --------------------------------------------------------------

def _zahl(wert) -> float:
    if isinstance(wert, bool):
        raise ValueError
    if isinstance(wert, (int, float)):
        zahl = float(wert)
    else:
        s = str(wert).strip().lower().replace("mm", "").replace(" ", "").replace(" ", "")
        if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", s):  # deutsches Tausenderformat: 3.090 / 3.090,5
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", ".")
        zahl = float(s)
    if not math.isfinite(zahl):
        raise ValueError
    return zahl


def _norm_mass(wert) -> str:
    """'100 x 16', '100X16', '100×16' -> '100x16'; 'r20' -> 'R20'. Verhindert doppelte Artikelgruppen durch Schreibweisen."""
    s = _text(wert)
    s = re.sub(r"\s*[x×X]\s*", "x", s)
    if re.fullmatch(r"[rR]\s*\d+([.,]\d+)?", s):
        s = "R" + re.sub(r"\s+", "", s[1:])
    return s


@dataclass
class Rohzeile:
    nr: int  # Excel-Zeilennummer
    profil: str
    mass: str
    material: str
    gruppe: str
    ort: str
    laenge: float
    menge: int
    preis: float
    einheit: str


def _lese_zeilen(zeilen: list, kopf_idx: int, spalten: dict[str, int]) -> tuple[list[Rohzeile], list[tuple[int, str]], int]:
    """Gibt (gueltige Zeilen, Fehler [(Excel-Zeile, Text)], Anzahl gelesener Datenzeilen) zurueck."""
    gueltig: list[Rohzeile] = []
    fehler: list[tuple[int, str]] = []
    gelesen = 0

    for idx in range(kopf_idx + 1, len(zeilen)):
        werte = zeilen[idx]
        nr = idx + 1

        def feld(name):
            pos = spalten.get(name)
            return werte[pos] if pos is not None and pos < len(werte) else None

        if all(_leer(feld(name)) for name in _SYNONYME):
            continue  # komplett leere Zeile
        gelesen += 1
        if gelesen > MAX_DATENZEILEN:
            raise ImportFehler(f"Die Datei hat mehr als {MAX_DATENZEILEN} Zeilen - bitte in kleinere Dateien aufteilen.")

        probleme: list[str] = []
        profil = _text(feld("profil"))
        mass = _norm_mass(feld("mass"))
        material = _text(feld("material")) or "---"  # "---" = unbekanntes Material (wie im bestehenden Bestand)
        ort = _text(feld("ort"))
        if not profil:
            probleme.append("Profil fehlt")
        if not mass:
            probleme.append("Mass fehlt")
        if not ort:
            probleme.append("Lagerort fehlt")

        laenge = 0.0
        try:
            laenge = _zahl(feld("laenge"))
            if laenge <= 0:
                probleme.append("Laenge muss groesser als 0 sein")
        except (ValueError, TypeError):
            probleme.append(f"Laenge '{_text(feld('laenge'))}' ist keine Zahl")

        menge = 1
        if not _leer(feld("menge")):
            try:
                menge_zahl = _zahl(feld("menge"))
                if menge_zahl < 1 or not menge_zahl.is_integer():
                    probleme.append("Menge muss eine ganze Zahl >= 1 sein")
                else:
                    menge = int(menge_zahl)
            except (ValueError, TypeError):
                probleme.append(f"Menge '{_text(feld('menge'))}' ist keine Zahl")

        preis = 0.0
        if not _leer(feld("preis")):
            try:
                preis = _zahl(feld("preis"))
                if preis < 0:
                    probleme.append("E-Preis darf nicht negativ sein")
            except (ValueError, TypeError):
                probleme.append(f"E-Preis '{_text(feld('preis'))}' ist keine Zahl")

        if probleme:
            fehler.append((nr, "; ".join(probleme)))
            continue

        gueltig.append(Rohzeile(
            nr=nr, profil=profil, mass=mass, material=material, gruppe=_text(feld("gruppe")),
            ort=ort, laenge=laenge, menge=menge, preis=preis, einheit=_text(feld("einheit")) or "Stk",
        ))
    return gueltig, fehler, gelesen


# --------------------------------------------------------------
# Ergebnis-Datenklassen
# --------------------------------------------------------------

@dataclass
class Position:
    nr: int  # Excel-Zeile
    bezeichnung: str
    barcode: str  # Haupt-Barcode (Artikelgruppe)
    barcode2: str  # Stueck-Barcode, leer bei uebersprungenen Zeilen
    ort: str
    laenge: float
    menge: int
    ziel: str  # "Artikel_Liste" oder "Reste"
    neue_gruppe: bool


@dataclass
class Aehnlich:
    """Ein unbekannter Name (Profil/Material/Lagerort), der einem bestehenden stark aehnelt -
    moeglicherweise ein Tippfehler. Der Anwender entscheidet: korrigieren oder wirklich neu."""
    feld: str  # "profil" | "material" | "ort"
    name: str  # so steht es in der Excel-Datei
    vorschlag: str  # der aehnliche, bereits bekannte Name
    zeilen: int = 0  # in wie vielen Excel-Zeilen der Name vorkommt
    entscheidung: str | None = None  # None = offen, "korrigieren" = Vorschlag nehmen, "neu" = neu anlegen


# Schluessel einer Entscheidung: (Feld, Name kleingeschrieben) -> "korrigieren" | "neu"
Entscheidungen = dict[tuple[str, str], str]


def entscheidungs_schluessel(feld: str, name: str) -> tuple[str, str]:
    return (feld, name.casefold())


@dataclass
class Analyse:
    gelesen: int = 0
    aehnliche: list[Aehnlich] = field(default_factory=list)
    fehler: list[tuple[int, str]] = field(default_factory=list)
    positionen: list[Position] = field(default_factory=list)  # werden importiert
    vorhandene: list[Position] = field(default_factory=list)  # uebersprungen, weil schon im Lager
    neue_profile: list[str] = field(default_factory=list)
    neue_materialien: list[str] = field(default_factory=list)
    neue_orte: list[str] = field(default_factory=list)
    neue_einheiten: list[str] = field(default_factory=list)
    neue_gruppen: list[str] = field(default_factory=list)


# --------------------------------------------------------------
# Kuerzel automatisch bilden
# --------------------------------------------------------------

def _neue_abkuerzung(name: str, laenge: int, vergeben: set[str]) -> str:
    """Bildet ein eindeutiges Barcode-Kuerzel fester Laenge aus dem Namen (Profil: 2, Material: 3 Zeichen)."""
    basis = re.sub(r"[^A-Z0-9]", "", name.upper()) or "UNBEKANNT"
    basis = basis.ljust(laenge, "X")
    kandidaten = [basis[:laenge]]
    kandidaten += [basis[: laenge - 1] + zeichen for zeichen in basis[laenge - 1:]]
    kandidaten += [basis[: laenge - 1] + str(i) for i in range(10)]
    kandidaten += [basis[: laenge - 2] + f"{i:02d}" for i in range(100)]
    for kandidat in kandidaten:
        if kandidat.upper() not in vergeben:
            return kandidat
    raise ImportFehler(f"Konnte kein freies Barcode-Kuerzel fuer '{name}' bilden.")


# --------------------------------------------------------------
# Aehnlichkeitspruefung (Tippfehler-Erkennung)
# --------------------------------------------------------------

AEHNLICHKEITS_SCHWELLE = 0.8  # 1.0 = identisch; 0.8 faengt z.B. 'Flacheisn' oder 'Saege unten ' ab


def _vergleichsform(name: str) -> str:
    s = name.casefold()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(alt, neu)
    return re.sub(r"[^a-z0-9]", "", s)


def _aehnlichster(name: str, kandidaten) -> str | None:
    """Der bekannte Name, der 'name' am staerksten aehnelt (ab Schwelle), sonst None."""
    gesucht = _vergleichsform(name)
    if len(gesucht) < 3:
        return None
    bester, beste_note = None, 0.0
    for kandidat in kandidaten:
        note = SequenceMatcher(None, gesucht, _vergleichsform(kandidat)).ratio()
        if note >= AEHNLICHKEITS_SCHWELLE and note > beste_note:
            bester, beste_note = kandidat, note
    return bester


# --------------------------------------------------------------
# Stand der Stammdaten (wird beim Durchrechnen mitgefuehrt)
# --------------------------------------------------------------

class _Stand:
    def __init__(self, q) -> None:
        """q ist db (Trockenlauf, liest) oder eine db.transaktion() (Import, liest + schreibt)."""
        self.orte = {r["OrtRegal"].casefold(): r["OrtRegal"] for r in q.fetch_all("SELECT OrtRegal FROM Lager")}
        self.profile = {
            r["Profil"].casefold(): (r["Profil"], r["Abkuerzung"])
            for r in q.fetch_all("SELECT Profil, Abkuerzung FROM Profil_Abk")
        }
        self.materialien = {
            r["Material"].casefold(): (r["Material"], r["Gruppe"], r["Abkuerzung"])
            for r in q.fetch_all("SELECT Material, Gruppe, Abkuerzung FROM Material_Gruppe")
        }
        self.einheiten = {r["Symbol"].casefold(): r["Symbol"] for r in q.fetch_all("SELECT Symbol FROM Einheit")}

        self.gruppen: dict[str, str] = {}  # Bezeichnung -> Barcode
        self.barcodes: list[str] = []
        for r in q.fetch_all("SELECT Barcode, Bezeichnung FROM Artikel_Gruppe"):
            self.gruppen[r["Bezeichnung"]] = r["Barcode"]
            self.barcodes.append(r["Barcode"])

        # Hoechste Stuecknummer je (Tabelle, Haupt-Barcode) und bereits vorhandene Stuecke
        self.nummern: dict[tuple[str, str], int] = {}
        self.vorhanden: set[tuple[str, float, str]] = set()
        for tabelle in ("Artikel_Liste", "Reste"):
            for r in q.fetch_all(f"SELECT Barcode, Barcode2, Bezeichnung, LaengeMM, OrtRegal FROM {tabelle}"):
                treffer = re.search(r"-(\d+)$", r["Barcode2"])
                if treffer:
                    schluessel = (tabelle, r["Barcode"])
                    self.nummern[schluessel] = max(self.nummern.get(schluessel, 0), int(treffer.group(1)))
                self.vorhanden.add((r["Bezeichnung"], round(float(r["LaengeMM"] or 0), 2), r["OrtRegal"]))

    # --- nachschlagen (ohne anzulegen) ---

    def finde_profil(self, name: str) -> str | None:
        eintrag = self.profile.get(name.casefold())
        if eintrag:
            return eintrag[0]
        for profil, abk in self.profile.values():  # auch das Kuerzel (z.B. "FL") wird erkannt
            if abk.casefold() == name.casefold():
                return profil
        return None

    def finde_material(self, name: str) -> str | None:
        eintrag = self.materialien.get(name.casefold())
        if eintrag:
            return eintrag[0]
        for material, _gruppe, abk in self.materialien.values():
            if abk.casefold() == name.casefold():
                return material
        return None

    def finde_ort(self, name: str) -> str | None:
        return self.orte.get(name.casefold())

    def profil_abk(self, profil: str) -> str:
        return self.profile[profil.casefold()][1]

    def material_info(self, material: str) -> tuple[str, str]:
        _name, gruppe, abk = self.materialien[material.casefold()]
        return gruppe, abk


def _verarbeite(
    q, rohzeilen: list[Rohzeile], grenze: float, ueberspringe_vorhandene: bool, schreiben: bool,
    entscheidungen: Entscheidungen | None = None,
) -> Analyse:
    stand = _Stand(q)
    analyse = Analyse()
    entscheidungen = entscheidungen or {}
    aehnliche: dict[tuple[str, str], Aehnlich] = {}
    datum = _dt.datetime.now().isoformat(timespec="seconds")

    def pruefe(feld: str, name: str, finde, bekannte) -> str:
        """Ist 'name' unbekannt, aber einem bekannten Namen sehr aehnlich, wird das gemerkt (-> Rueckfrage in
        der Oberflaeche). Hat der Anwender 'korrigieren' gewaehlt, wird der bekannte Name verwendet."""
        if finde(name) is not None:
            return name
        vorschlag = _aehnlichster(name, bekannte())
        if vorschlag is None:
            return name
        schluessel = entscheidungs_schluessel(feld, name)
        eintrag = aehnliche.setdefault(
            schluessel, Aehnlich(feld, name, vorschlag, 0, entscheidungen.get(schluessel))
        )
        eintrag.zeilen += 1
        return eintrag.vorschlag if eintrag.entscheidung == "korrigieren" else name

    for r in rohzeilen:
        p_name = pruefe("profil", r.profil, stand.finde_profil, lambda: [p for p, _a in stand.profile.values()])
        m_name = pruefe("material", r.material, stand.finde_material, lambda: [m for m, _g, _a in stand.materialien.values()])
        o_name = pruefe("ort", r.ort, stand.finde_ort, lambda: list(stand.orte.values()))

        profil = stand.finde_profil(p_name)
        material = stand.finde_material(m_name)
        ort = stand.finde_ort(o_name)

        # Schon im Lager? (gleiche Artikelgruppe, Laenge und Lagerort) -> optional ueberspringen,
        # und zwar bevor dafuer irgendetwas Neues angelegt wird.
        if ueberspringe_vorhandene and profil and material and ort:
            bezeichnung = f"{profil}-{r.mass}-{material}"
            if (bezeichnung, round(r.laenge, 2), ort) in stand.vorhanden:
                analyse.vorhandene.append(Position(
                    r.nr, bezeichnung, stand.gruppen.get(bezeichnung, ""), "", ort, r.laenge, r.menge,
                    "Reste" if 0 < r.laenge <= grenze else "Artikel_Liste", False,
                ))
                continue

        # --- fehlende Stammdaten anlegen ---
        if profil is None:
            abk = _neue_abkuerzung(p_name, 2, {a.upper() for _p, a in stand.profile.values()})
            stand.profile[p_name.casefold()] = (p_name, abk)
            profil = p_name
            analyse.neue_profile.append(f"{profil} (Kuerzel {abk})")
            if schreiben:
                q.execute("INSERT INTO Profil_Abk (Profil, Abkuerzung) VALUES (?, ?)", (profil, abk))
        if material is None:
            abk = _neue_abkuerzung(m_name, 3, {a.upper() for _m, _g, a in stand.materialien.values()})
            gruppe = r.gruppe or "Unbekannt"
            stand.materialien[m_name.casefold()] = (m_name, gruppe, abk)
            material = m_name
            analyse.neue_materialien.append(f"{material} (Gruppe {gruppe}, Kuerzel {abk})")
            if schreiben:
                q.execute(
                    "INSERT INTO Material_Gruppe (Material, Gruppe, Abkuerzung) VALUES (?, ?, ?)",
                    (material, gruppe, abk),
                )
        if ort is None:
            stand.orte[o_name.casefold()] = o_name
            ort = o_name
            analyse.neue_orte.append(ort)
            if schreiben:
                q.execute("INSERT INTO Lager (OrtRegal) VALUES (?)", (ort,))
        einheit = stand.einheiten.get(r.einheit.casefold())
        if einheit is None:
            stand.einheiten[r.einheit.casefold()] = r.einheit
            einheit = r.einheit
            analyse.neue_einheiten.append(einheit)
            if schreiben:
                q.execute("INSERT INTO Einheit (Symbol) VALUES (?)", (einheit,))

        # --- Artikelgruppe finden oder anlegen ---
        bezeichnung = f"{profil}-{r.mass}-{material}"
        material_gruppe, material_abk = stand.material_info(material)
        barcode = stand.gruppen.get(bezeichnung)
        neue_gruppe = barcode is None
        if neue_gruppe:
            prefix = stand.profil_abk(profil) + material_abk
            hoechste = max(
                (int(b[len(prefix):]) for b in stand.barcodes if b.startswith(prefix) and b[len(prefix):].isdigit()),
                default=0,
            )
            barcode = f"{prefix}{hoechste + 1:04d}"
            stand.gruppen[bezeichnung] = barcode
            stand.barcodes.append(barcode)
            analyse.neue_gruppen.append(f"{bezeichnung} ({barcode})")
            if schreiben:
                q.execute(
                    "INSERT INTO Artikel_Gruppe (Barcode, Bezeichnung, Profil, Mass, Material) VALUES (?, ?, ?, ?, ?)",
                    (barcode, bezeichnung, profil, r.mass, material),
                )

        # --- Stueck einbuchen (Voll/Rest wie beim manuellen Hinzufuegen) ---
        ist_rest = 0 < r.laenge <= grenze
        ziel, typ = ("Reste", "Rest") if ist_rest else ("Artikel_Liste", "Voll")
        schluessel = (ziel, barcode)
        stand.nummern[schluessel] = stand.nummern.get(schluessel, 0) + 1
        barcode2 = f"{barcode}-{stand.nummern[schluessel]}"

        if schreiben:
            werte = (
                datum, barcode, barcode2, bezeichnung, profil, r.mass, r.laenge, material_gruppe, material,
                ort, typ, r.menge, r.preis, einheit,
            )
            spalten = (
                "Datum, Barcode, Barcode2, Bezeichnung, Profil, Mass, LaengeMM, MaterialGruppe, Material, "
                "OrtRegal, Typ, MengeStueck, EPreis, EPreisEinheit"
            )
            platzhalter = ", ".join("?" * len(werte))
            q.execute(f"INSERT INTO {ziel} ({spalten}) VALUES ({platzhalter})", werte)
            q.execute(f"INSERT INTO Verlauf ({spalten}) VALUES ({platzhalter})", werte)

        analyse.positionen.append(
            Position(r.nr, bezeichnung, barcode, barcode2, ort, r.laenge, r.menge, ziel, neue_gruppe)
        )
    analyse.aehnliche = list(aehnliche.values())
    return analyse


# --------------------------------------------------------------
# Oeffentliche Funktionen
# --------------------------------------------------------------

def offene_rueckfragen(analyse: Analyse) -> list[Aehnlich]:
    """Aehnliche Namen, ueber die der Anwender noch nicht entschieden hat."""
    return [a for a in analyse.aehnliche if a.entscheidung is None]


def analysiere(
    daten: bytes, ueberspringe_vorhandene: bool = True, entscheidungen: Entscheidungen | None = None,
) -> Analyse:
    """Trockenlauf: liest und prueft die Datei und zeigt, was importiert wuerde. Schreibt nichts.
    'entscheidungen' enthaelt die Antworten auf Aehnlichkeits-Rueckfragen (siehe Aehnlich)."""
    zeilen, kopf_idx, spalten = _lese_blatt(daten)
    rohzeilen, fehler, gelesen = _lese_zeilen(zeilen, kopf_idx, spalten)
    analyse = _verarbeite(
        db, rohzeilen, logic.schrott_grenze_mm(), ueberspringe_vorhandene, schreiben=False,
        entscheidungen=entscheidungen,
    )
    analyse.gelesen = gelesen
    analyse.fehler = fehler
    return analyse


def importiere(
    daten: bytes, ueberspringe_vorhandene: bool = True, entscheidungen: Entscheidungen | None = None,
) -> Analyse:
    """Bucht alle gueltigen Zeilen ein - alles in einer Transaktion (ganz oder gar nicht).
    Zeilen mit Fehlern werden nie importiert; die Entscheidung, ob trotzdem importiert wird,
    trifft die Oberflaeche. Solange eine Aehnlichkeits-Rueckfrage offen ist, wird nichts eingebucht."""
    zeilen, kopf_idx, spalten = _lese_blatt(daten)
    rohzeilen, fehler, gelesen = _lese_zeilen(zeilen, kopf_idx, spalten)
    grenze = logic.schrott_grenze_mm()
    with logic._SCHREIB_LOCK, db.transaktion() as tx:
        analyse = _verarbeite(
            tx, rohzeilen, grenze, ueberspringe_vorhandene, schreiben=True, entscheidungen=entscheidungen,
        )
        offen = offene_rueckfragen(analyse)
        if offen:  # Exception im with-Block -> Rollback, es bleibt nichts zurueck
            namen = ", ".join(f"'{a.name}'" for a in offen)
            raise ImportFehler(f"Es gibt noch offene Rueckfragen zu aehnlichen Namen: {namen}.")
    analyse.gelesen = gelesen
    analyse.fehler = fehler
    return analyse


def vorlage_bytes() -> bytes:
    """Leere Excel-Vorlage mit den erwarteten Spalten und einer kurzen Anleitung."""
    mappe = openpyxl.Workbook()
    blatt = mappe.active
    blatt.title = "Artikel"
    kopf = ["Profil", "Mass", "Material", "Laenge_mm", "Menge", "Lagerort", "E-Preis", "E-Preis-Einheit"]
    blatt.append(kopf)
    for zelle in blatt[1]:
        zelle.font = Font(bold=True)
    for spalte, breite in zip("ABCDEFGH", (18, 12, 14, 12, 8, 28, 10, 16)):
        blatt.column_dimensions[spalte].width = breite
    blatt.freeze_panes = "A2"

    hilfe = mappe.create_sheet("Anleitung")
    zeilen = [
        "Pro Zeile ein Stueck (eine Stange) - ab Zeile 2 im Blatt 'Artikel' eintragen.",
        "",
        "Pflicht: Profil (z.B. Flacheisen), Mass (z.B. 40x10 oder R20), Material (z.B. ST37K),",
        "         Laenge_mm (z.B. 3040), Lagerort (z.B. Saege unten).",
        "Optional: Menge (leer = 1), E-Preis (leer = 0), E-Preis-Einheit (leer = Stk).",
        "",
        "Material leer lassen = unbekanntes Material ('---').",
        "Unbekannte Profile, Materialien, Lagerorte und Artikelgruppen werden automatisch angelegt.",
        "Laenge <= Rest-Grenze (Einstellungen -> Schwellenwerte) wird automatisch als Rest gespeichert.",
        "Die Reihenfolge der Spalten ist egal, die Ueberschriften muessen aber vorhanden sein.",
    ]
    for zeile in zeilen:
        hilfe.append([zeile])
    hilfe.column_dimensions["A"].width = 100

    puffer = io.BytesIO()
    mappe.save(puffer)
    return puffer.getvalue()

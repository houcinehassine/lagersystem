"""Geschaeftslogik des Lager Systems.

Portierung der VBA-Module F (Artikelgruppe), G (Artikel-Stueck + Entnahme)
und E (Profil/Material-Lookup) nach Python. Die Funktionsnamen orientieren
sich bewusst an den Originalen, damit der Vergleich mit dem alten VBA-Code
leicht faellt.
"""
from __future__ import annotations

import datetime as _dt
import re
import threading

import pandas as pd

import db

SCHROTT_GRENZE_STANDARD_MM = 1000  # Fallback, falls noch nicht in den Einstellungen gesetzt


def schrott_grenze_mm() -> float:
    """EINE gemeinsame, einstellbare Laengen-Schwelle (mm) fuer zwei Stellen:
    1. Bei einer Entnahme: liegt die Restlaenge darunter, wird nachgefragt / landet sie in 'Reste'.
    2. Beim manuellen Hinzufuegen neuer Ware: liegt die Laenge darunter, gilt das Stueck
       automatisch als 'Rest' statt als voller Artikel.
    Einstellbar unter Einstellungen -> Schwellenwerte."""
    return db.hole_konfiguration("SchrottGrenzeMM", SCHROTT_GRENZE_STANDARD_MM)

# Schuetzt "Hoechste Nummer suchen + neuen Barcode einfuegen" vor Race-Conditions,
# wenn mehrere Nutzer im Netzwerk gleichzeitig auf denselben Streamlit-Prozess zugreifen.
_SCHREIB_LOCK = threading.Lock()


class LagerFehler(Exception):
    """Fachliche Fehler (z.B. Duplikat, nicht gefunden) - werden in der UI als Meldung gezeigt."""


# --------------------------------------------------------------
# E-Module: Profil / Material Lookups
# --------------------------------------------------------------

def hole_profil_abkuerzung(profil: str) -> str:
    row = db.fetch_one("SELECT Abkuerzung FROM Profil_Abk WHERE Profil = ?", (profil,))
    return row["Abkuerzung"] if row else "XXX"


def hole_material_abkuerzung(material: str) -> str:
    row = db.fetch_one("SELECT Abkuerzung FROM Material_Gruppe WHERE Material = ?", (material,))
    return row["Abkuerzung"] if row else "XXX"


def hole_material_gruppe(material: str) -> str:
    row = db.fetch_one("SELECT Gruppe FROM Material_Gruppe WHERE Material = ?", (material,))
    return row["Gruppe"] if row else ""


# --------------------------------------------------------------
# F-Module: Artikelgruppe (Stammdaten, Haupt-Barcode)
# --------------------------------------------------------------

def make_barcode_ag(profil: str, mass: str, material: str) -> str:
    """Entspricht MakeBarcode_AG: Praefix (Profil+Material-Kuerzel) + naechste 4-stellige Nummer."""
    prefix = hole_profil_abkuerzung(profil) + hole_material_abkuerzung(material)
    rows = db.fetch_all("SELECT Barcode FROM Artikel_Gruppe WHERE Barcode LIKE ?", (prefix + "%",))
    max_nummer = 0
    for row in rows:
        suffix = row["Barcode"][len(prefix):]
        if suffix.isdigit():
            max_nummer = max(max_nummer, int(suffix))
    return f"{prefix}{max_nummer + 1:04d}"


def create_artikel_gruppe(profil: str, mass: str, material: str) -> str:
    """Entspricht MakeArtikelGruppe: prueft Duplikat, generiert Barcode, legt Zeile an."""
    bezeichnung = f"{profil}-{mass}-{material}"
    with _SCHREIB_LOCK:
        if db.value_exists("Artikel_Gruppe", "Bezeichnung", bezeichnung):
            raise LagerFehler(f"Dieser Artikel existiert bereits: {bezeichnung}")

        barcode = make_barcode_ag(profil, mass, material)
        db.execute(
            "INSERT INTO Artikel_Gruppe (Barcode, Bezeichnung, Profil, Mass, Material) VALUES (?, ?, ?, ?, ?)",
            (barcode, bezeichnung, profil, mass, material),
        )
    return barcode


def hole_daten_ag(barcode: str) -> dict | None:
    row = db.fetch_one("SELECT * FROM Artikel_Gruppe WHERE Barcode = ?", (barcode,))
    return dict(row) if row else None


# --------------------------------------------------------------
# G-Module: Artikel-Stueck (Zugang, Bearbeiten, Loeschen)
# --------------------------------------------------------------

def _naechste_stueck_nummer(table: str, haupt_barcode: str) -> int:
    """Entspricht MakeBarcode_AS: sucht die hoechste Stuecknummer fuer diesen Haupt-Barcode
    INNERHALB der jeweiligen Tabelle (Artikel_Liste und Reste zaehlen unabhaengig, wie im Original)."""
    rows = db.fetch_all(f"SELECT Barcode2 FROM {table} WHERE Barcode = ?", (haupt_barcode,))
    max_nummer = 0
    for row in rows:
        match = re.search(r"-(\d+)$", row["Barcode2"])
        if match:
            max_nummer = max(max_nummer, int(match.group(1)))
    return max_nummer + 1


def make_barcode_as(table: str, haupt_barcode: str) -> str:
    return f"{haupt_barcode}-{_naechste_stueck_nummer(table, haupt_barcode)}"


def add_artikel_stueck(
    table: str,
    haupt_barcode: str,
    ort: str,
    typ: str,
    laenge_mm: float,
    menge: int,
    e_preis: float,
    e_preis_einheit: str,
) -> str:
    """Entspricht MakeNew_ArtikelStueck: holt Stammdaten aus Artikel_Gruppe, legt neues Stueck an."""
    ag = hole_daten_ag(haupt_barcode)
    if ag is None:
        raise LagerFehler(f"Der Barcode '{haupt_barcode}' wurde in der Artikel_Gruppe nicht gefunden!")

    with _SCHREIB_LOCK:
        barcode2 = make_barcode_as(table, haupt_barcode)
        datum = _dt.datetime.now().isoformat(timespec="seconds")

        db.execute(
            f"""INSERT INTO {table}
                (Datum, Barcode, Barcode2, Bezeichnung, Profil, Mass, LaengeMM,
                 MaterialGruppe, Material, OrtRegal, Typ, MengeStueck, EPreis, EPreisEinheit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datum, haupt_barcode, barcode2, ag["Bezeichnung"], ag["Profil"], ag["Mass"],
                laenge_mm or None, hole_material_gruppe(ag["Material"]), ag["Material"],
                ort, typ, menge, e_preis, e_preis_einheit,
            ),
        )
        _schreibe_verlauf(
            haupt_barcode, barcode2, ag["Bezeichnung"], ag["Profil"], ag["Mass"],
            laenge_mm or 0, hole_material_gruppe(ag["Material"]), ag["Material"],
            ort, typ, menge, e_preis, e_preis_einheit,
        )
    return barcode2


def delete_artikel_stueck(table: str, barcode2: str) -> None:
    row = db.fetch_one(f"SELECT ID FROM {table} WHERE Barcode2 = ?", (barcode2,))
    if row is None:
        raise LagerFehler(f"Artikel mit Barcode '{barcode2}' nicht gefunden.")
    db.execute(f"DELETE FROM {table} WHERE Barcode2 = ?", (barcode2,))


# --------------------------------------------------------------
# Papierkorb: "Loeschen" in der UI verschiebt ein Stueck hierher statt es
# sofort zu entfernen - kann von hier wiederhergestellt oder endgueltig
# geloescht werden.
# --------------------------------------------------------------

def soft_delete_artikel_stueck(table: str, barcode2: str) -> None:
    """Verschiebt ein Stueck in den Papierkorb, statt es sofort zu loeschen."""
    zeile = db.fetch_one(f"SELECT * FROM {table} WHERE Barcode2 = ?", (barcode2,))
    if zeile is None:
        raise LagerFehler(f"Artikel mit Barcode '{barcode2}' nicht gefunden.")

    geloescht_am = _dt.datetime.now().isoformat(timespec="seconds")
    db.execute(
        """INSERT INTO Papierkorb
           (QuellTabelle, GeloeschtAm, Datum, Barcode, Barcode2, Bezeichnung, Profil, Mass, LaengeMM,
            MaterialGruppe, Material, OrtRegal, Typ, MengeStueck, EPreis, EPreisEinheit)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            table, geloescht_am, zeile["Datum"], zeile["Barcode"], zeile["Barcode2"], zeile["Bezeichnung"],
            zeile["Profil"], zeile["Mass"], zeile["LaengeMM"], zeile["MaterialGruppe"], zeile["Material"],
            zeile["OrtRegal"], zeile["Typ"], zeile["MengeStueck"], zeile["EPreis"], zeile["EPreisEinheit"],
        ),
    )
    db.execute(f"DELETE FROM {table} WHERE Barcode2 = ?", (barcode2,))


def papierkorb_wiederherstellen(papierkorb_id: int) -> None:
    """Legt ein Papierkorb-Stueck wieder in seiner urspruenglichen Tabelle an."""
    zeile = db.fetch_one("SELECT * FROM Papierkorb WHERE ID = ?", (papierkorb_id,))
    if zeile is None:
        raise LagerFehler("Eintrag im Papierkorb nicht gefunden.")

    ziel_table = zeile["QuellTabelle"]
    if db.value_exists(ziel_table, "Barcode2", zeile["Barcode2"]):
        raise LagerFehler(
            f"'{zeile['Barcode2']}' existiert bereits wieder in {ziel_table.replace('_', ' ')} - "
            "nicht wiederhergestellt."
        )

    db.execute(
        f"""INSERT INTO {ziel_table}
            (Datum, Barcode, Barcode2, Bezeichnung, Profil, Mass, LaengeMM,
             MaterialGruppe, Material, OrtRegal, Typ, MengeStueck, EPreis, EPreisEinheit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            zeile["Datum"], zeile["Barcode"], zeile["Barcode2"], zeile["Bezeichnung"], zeile["Profil"],
            zeile["Mass"], zeile["LaengeMM"], zeile["MaterialGruppe"], zeile["Material"], zeile["OrtRegal"],
            zeile["Typ"], zeile["MengeStueck"], zeile["EPreis"], zeile["EPreisEinheit"],
        ),
    )
    db.execute("DELETE FROM Papierkorb WHERE ID = ?", (papierkorb_id,))


def papierkorb_endgueltig_loeschen(papierkorb_id: int) -> None:
    db.execute("DELETE FROM Papierkorb WHERE ID = ?", (papierkorb_id,))


def edit_artikel_stueck(table: str, barcode2: str, **felder) -> None:
    """felder z.B. LaengeMM=500, OrtRegal='A1', Typ='Voll', MengeStueck=2, EPreis=1.5, EPreisEinheit='Stk'"""
    if not felder:
        return
    if db.fetch_one(f"SELECT ID FROM {table} WHERE Barcode2 = ?", (barcode2,)) is None:
        raise LagerFehler(f"Artikel mit Barcode '{barcode2}' nicht gefunden.")
    zuweisungen = ", ".join(f"{spalte} = ?" for spalte in felder)
    db.execute(f"UPDATE {table} SET {zuweisungen} WHERE Barcode2 = ?", (*felder.values(), barcode2))


# --------------------------------------------------------------
# G7: Materialentnahme-Logik (Kernstueck des Systems)
# --------------------------------------------------------------

def berechne_restlaenge(initiale_laenge: float, genutzte_laenge: float) -> float:
    rest = initiale_laenge - genutzte_laenge
    if rest < 0:
        raise LagerFehler("Die genutzte Laenge kann nicht groesser als die urspruengliche Laenge sein.")
    return rest


def ist_schrott_kandidat(restlaenge: float) -> bool:
    """Entspricht der VBA-Schrott-Abfrage: Reststueck ist zu klein zum sinnvollen Weiterverwenden."""
    return 0 < restlaenge < schrott_grenze_mm()


def process_material_entnahme(
    source_table: str,
    urspungs_barcode2: str,
    genutzte_laenge: float,
    ist_schrott: bool,
) -> str:
    """Entspricht ProzessMaterialEntnahme: bucht eine Entnahme, reduziert/loescht das Ursprungsstueck,
    legt bei Bedarf ein Reststueck an (in "Reste" bei < 1000mm, sonst zurueck in "Artikel_Liste")."""
    with _SCHREIB_LOCK:
        orig = db.fetch_one(f"SELECT * FROM {source_table} WHERE Barcode2 = ?", (urspungs_barcode2,))
        if orig is None:
            raise LagerFehler(f"Ursprungsstueck '{urspungs_barcode2}' nicht gefunden.")

        initiale_laenge = orig["LaengeMM"] or 0
        restlaenge = berechne_restlaenge(initiale_laenge, genutzte_laenge)

        # 1. Verlauf-Eintrag VOR dem Reduzieren (negative Laenge = Verbrauch)
        _schreibe_verlauf(
            orig["Barcode"], orig["Barcode2"], orig["Bezeichnung"], orig["Profil"], orig["Mass"],
            -genutzte_laenge, orig["MaterialGruppe"], orig["Material"], orig["OrtRegal"],
            "Verbrauch", 1, orig["EPreis"], orig["EPreisEinheit"],
        )

        # 2. Ursprungsstueck reduzieren oder loeschen
        if (orig["MengeStueck"] or 1) > 1:
            db.execute(
                f"UPDATE {source_table} SET MengeStueck = MengeStueck - 1 WHERE Barcode2 = ?",
                (urspungs_barcode2,),
            )
        else:
            db.execute(f"DELETE FROM {source_table} WHERE Barcode2 = ?", (urspungs_barcode2,))

        # 3. Reststueck einbuchen, falls vorhanden und kein Schrott
        if restlaenge > 0 and not ist_schrott:
            ziel_table = "Reste" if restlaenge < schrott_grenze_mm() else "Artikel_Liste"
            _buche_reststueck_ein(ziel_table, orig, restlaenge)

    return f"Materialentnahme erfolgreich verbucht. Restlaenge: {restlaenge:.0f} mm" if restlaenge > 0 else \
           "Materialentnahme erfolgreich verbucht (kein Reststueck)."


def _buche_reststueck_ein(ziel_table: str, orig: db.sqlite3.Row, neue_laenge: float) -> None:
    """Entspricht BucheRestStueckEin: sucht identisches Reststueck (gleicher Haupt-Barcode + Laenge),
    erhoeht sonst die Menge, sonst legt es ein neues Stueck mit neuem Barcode2 an."""
    passendes = db.fetch_one(
        f"SELECT ID, MengeStueck FROM {ziel_table} WHERE Barcode = ? AND LaengeMM = ?",
        (orig["Barcode"], neue_laenge),
    )
    if passendes is not None:
        db.execute(
            f"UPDATE {ziel_table} SET MengeStueck = MengeStueck + 1 WHERE ID = ?",
            (passendes["ID"],),
        )
        return

    neuer_barcode2 = make_barcode_as(ziel_table, orig["Barcode"])
    datum = _dt.datetime.now().isoformat(timespec="seconds")
    db.execute(
        f"""INSERT INTO {ziel_table}
            (Datum, Barcode, Barcode2, Bezeichnung, Profil, Mass, LaengeMM,
             MaterialGruppe, Material, OrtRegal, Typ, MengeStueck, EPreis, EPreisEinheit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
        (
            datum, orig["Barcode"], neuer_barcode2, orig["Bezeichnung"], orig["Profil"], orig["Mass"],
            neue_laenge, orig["MaterialGruppe"], orig["Material"], orig["OrtRegal"],
            "Rest", orig["EPreis"], orig["EPreisEinheit"],
        ),
    )


def _schreibe_verlauf(
    barcode, barcode2, bezeichnung, profil, mass, laenge_mm,
    material_gruppe, material, ort, typ, menge, e_preis, e_preis_einheit,
) -> None:
    datum = _dt.datetime.now().isoformat(timespec="seconds")
    db.execute(
        """INSERT INTO Verlauf
           (Datum, Barcode, Barcode2, Bezeichnung, Profil, Mass, LaengeMM,
            MaterialGruppe, Material, OrtRegal, Typ, MengeStueck, EPreis, EPreisEinheit)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datum, barcode, barcode2, bezeichnung, profil, mass, laenge_mm,
            material_gruppe, material, ort, typ, menge, e_preis, e_preis_einheit,
        ),
    )


# --------------------------------------------------------------
# H-Module: Suche
# --------------------------------------------------------------

def suche(begriff: str, nach: str = "Barcode") -> dict[str, "db.pd.DataFrame"]:
    """Entspricht Fill_Dashboard_List / BtnSuche_Click: durchsucht Artikel_Liste und Reste.

    Bei nach='Barcode' wird sowohl der Haupt-Barcode als auch der Stueck-Barcode
    (Barcode2) geprueft, damit ein gescannter Stueck-Code (z.B. 'FLS370010-1')
    genauso gefunden wird wie der Gruppen-Code."""
    muster = f"%{begriff}%"
    ergebnisse = {}
    for table in ("Artikel_Liste", "Reste"):
        if nach == "Barcode":
            query = f"SELECT * FROM {table} WHERE Barcode LIKE ? OR Barcode2 LIKE ?"
            params = (muster, muster)
        else:
            query = f"SELECT * FROM {table} WHERE Bezeichnung LIKE ?"
            params = (muster,)
        ergebnisse[table] = db.fetch_df(query, params)
    return ergebnisse


def distinct_werte(spalte: str) -> list[str]:
    """Eindeutige, nicht-leere Werte einer Spalte ueber Artikel_Liste UND Reste - fuer Dropdowns."""
    query = f"""
        SELECT DISTINCT {spalte} AS wert FROM Artikel_Liste WHERE {spalte} IS NOT NULL AND {spalte} != ''
        UNION
        SELECT DISTINCT {spalte} AS wert FROM Reste WHERE {spalte} IS NOT NULL AND {spalte} != ''
        ORDER BY wert
    """
    return [row["wert"] for row in db.fetch_all(query)]


def erweiterte_suche(
    profil: str = "", barcode: str = "", bezeichnung: str = "", ort: str = "",
    material: str = "", mass: str = "", laenge_von: float = 0, laenge_bis: float = 0,
) -> dict[str, "db.pd.DataFrame"]:
    """Filtert Artikel_Liste und Reste ueber mehrere gleichzeitig aktive Kriterien (UND-verknuepft).
    Leere/0-Werte werden ignoriert (kein Filter auf dieses Feld)."""
    ergebnisse = {}
    for table in ("Artikel_Liste", "Reste"):
        bedingungen = []
        params: list = []
        if profil:
            bedingungen.append("Profil = ?")
            params.append(profil)
        if barcode:
            bedingungen.append("(Barcode LIKE ? OR Barcode2 LIKE ?)")
            params += [f"%{barcode}%", f"%{barcode}%"]
        if bezeichnung:
            bedingungen.append("Bezeichnung LIKE ?")
            params.append(f"%{bezeichnung}%")
        if ort:
            bedingungen.append("OrtRegal = ?")
            params.append(ort)
        if material:
            bedingungen.append("Material = ?")
            params.append(material)
        if mass:
            bedingungen.append("Mass = ?")
            params.append(mass)
        if laenge_von:
            bedingungen.append("LaengeMM >= ?")
            params.append(laenge_von)
        if laenge_bis:
            bedingungen.append("LaengeMM <= ?")
            params.append(laenge_bis)

        where = " AND ".join(bedingungen) if bedingungen else "1=1"
        ergebnisse[table] = db.fetch_df(f"SELECT * FROM {table} WHERE {where}", tuple(params))
    return ergebnisse


# --------------------------------------------------------------
# B-Module: Export
# --------------------------------------------------------------

EXPORTIERBARE_TABELLEN = ["Artikel_Liste", "Reste", "Verlauf", "Artikel_Gruppe"]


def export_excel_bytes(tabellen: list[str]) -> bytes:
    """Entspricht DashboardExport/ExportiereExcel: baut eine .xlsx-Datei mit einem Blatt
    pro gewaehlter Tabelle und gibt die Rohdaten zurueck (zum Download in der UI)."""
    import io

    puffer = io.BytesIO()
    with pd.ExcelWriter(puffer, engine="openpyxl") as writer:
        for tabelle in tabellen:
            db.fetch_df(f"SELECT * FROM {tabelle}").to_excel(writer, sheet_name=tabelle, index=False)
    return puffer.getvalue()


def _pdf_tabellen_seite(pdf, titel: str, df: pd.DataFrame) -> None:
    """Rendert eine Tabelle (DataFrame) als eigene Seite in ein bereits geoeffnetes FPDF-Objekt."""
    from fpdf.fonts import FontFace

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, titel, new_x="LMARGIN", new_y="NEXT")

    if df.empty:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, "Keine Eintraege vorhanden.")
        return

    pdf.set_font("Helvetica", "", 6)
    spalten = [str(c) for c in df.columns]
    zeilen = df.fillna("").astype(str).values.tolist()
    with pdf.table(headings_style=FontFace(emphasis="BOLD", size_pt=6)) as table:
        table.row(spalten)
        for zeile in zeilen:
            table.row(zeile)


def export_pdf_bytes(tabellen: list[str]) -> bytes:
    """Entspricht ExportierePDF: eine Querformat-PDF mit einer Seite pro gewaehlter Tabelle."""
    from fpdf import FPDF

    pdf = FPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(auto=True, margin=10)
    for tabelle in tabellen:
        df = db.fetch_df(f"SELECT * FROM {tabelle}")
        _pdf_tabellen_seite(pdf, tabelle.replace("_", " "), df)
    return bytes(pdf.output())


def export_pdf_bytes_df(df: pd.DataFrame, titel: str) -> bytes:
    """Wie export_pdf_bytes, aber fuer eine beliebige bereits geladene Tabelle (z.B. eine
    Einstellungen-Stammdatentabelle oder ein Suchergebnis) - eine einzelne PDF-Seite."""
    from fpdf import FPDF

    pdf = FPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(auto=True, margin=10)
    _pdf_tabellen_seite(pdf, titel, df)
    return bytes(pdf.output())


# --------------------------------------------------------------
# C-Module: Email-Entwurf (mailto, ohne SMTP-Zugangsdaten)
# --------------------------------------------------------------

def hole_email_betreff(tabellen: list[str]) -> str:
    """Entspricht HoleEmailBetreff: 'Lager_System - Stand: DD.MM.YYYY'."""
    if set(tabellen) == set(EXPORTIERBARE_TABELLEN):
        basis = "Lager_System"
    else:
        basis = "+".join(t.replace("_", "") for t in tabellen)
    return f"{basis} - Stand: {_dt.date.today():%d.%m.%Y}"


def hole_email_text(tabellen: list[str]) -> str:
    """Entspricht HoleEmailText: Standardtext mit Liste der exportierten Tabellen."""
    zeilen = "\n".join(f"- {t}" for t in tabellen)
    jetzt = _dt.datetime.now()
    return (
        "Hallo,\n\n"
        "anbei erhalten Sie die angeforderte(n) Lagerliste(n) als Anhang.\n\n"
        f"Exportierte Tabellen:\n{zeilen}\n\n"
        f"Der Export wurde heute, {jetzt:%d.%m.%Y} um {jetzt:%H:%M} erstellt.\n\n"
        "Bitte die zuvor heruntergeladene Datei manuell an diese E-Mail anhaengen "
        "(Browser koennen das aus Sicherheitsgruenden nicht automatisch tun).\n\n"
        "Mit freundlichen Gruessen"
    )

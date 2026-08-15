"""Lager System - Streamlit-Oberflaeche.

Ersetzt die Excel-Blaetter Dashboard / Artikel Liste / Reste / Verlauf /
Artikel Gruppe / Einstellung durch Seiten dieser App. Die zugrundeliegende
Logik lebt in logic.py, der Datenzugriff in db.py.
"""
from __future__ import annotations

import urllib.parse

import pandas as pd
import streamlit as st

import db
import logic

st.set_page_config(page_title="Lager System", layout="wide")
db.init_db()

# Zentriert alle st.dialog-Fenster vertikal in der Mitte des Bildschirms
# (Streamlit richtet sie standardmaessig oben aus). Ausserdem Ueberschriften
# (Seitentitel = h1, Abschnitts-Ueberschriften = h2/h3) eine Stufe kleiner.
st.markdown(
    """<style>
    [data-testid="stDialog"] > div { align-items: center !important; }
    h1 { font-size: 22px !important; }
    h2, h3 { font-size: 17px !important; }
    </style>""",
    unsafe_allow_html=True,
)


# --------------------------------------------------------------
# Hilfsfunktionen fuer wiederkehrende UI-Bausteine
# --------------------------------------------------------------

def lookup_liste(query: str) -> list[str]:
    return [row[0] for row in db.fetch_all(query)]


def segmented_nav(label: str, optionen: list[str], key: str) -> str:
    """Wie st.segmented_control, initialisiert den Wert aber sicher vor dem ersten Rendern."""
    if key not in st.session_state:
        st.session_state[key] = optionen[0]
    return st.segmented_control(label, optionen, key=key)


def volle_hoehe(df: pd.DataFrame) -> int:
    """Hoehe in Pixeln, die eine st.dataframe braucht, um ALLE Zeilen ohne eigenen
    Scrollbalken zu zeigen - die Seite selbst scrollt dann stattdessen."""
    zeilenhoehe = 35
    kopfhoehe = 38
    puffer = 3
    return kopfhoehe + zeilenhoehe * len(df) + puffer


def pdf_download_button(df: pd.DataFrame, titel: str, key: str, label: str = "📄 Als PDF herunterladen") -> None:
    """PDF-Download-Knopf fuer eine beliebige Tabelle - CSV gibt es bereits automatisch
    ueber das Symbol-Menue oben rechts in jeder st.dataframe (Streamlit-Bordmittel, nicht erweiterbar)."""
    st.download_button(
        label,
        data=logic.export_pdf_bytes_df(df, titel),
        file_name=f"{titel}_{pd.Timestamp.now():%y-%m-%d_%H-%M}.pdf",
        mime="application/pdf",
        key=key,
        use_container_width=True,
    )


def zeige_tabelle(table: str, titel: str, order_by: str | None = None) -> None:
    query = f"SELECT * FROM {table}" + (f" ORDER BY {order_by}" if order_by else "")
    df = db.fetch_df(query)
    col_titel, col_pdf = st.columns([5, 1])
    col_titel.subheader(f"{titel} ({len(df)})")
    if df.empty:
        st.info("Noch keine Eintraege vorhanden.")
    else:
        with col_pdf:
            st.write("")  # richtet den Button vertikal auf Hoehe der Ueberschrift aus
            pdf_download_button(df, titel, key=f"pdf_{table}_{titel}", label="📄 PDF")
        st.dataframe(df, use_container_width=True, hide_index=True, height=volle_hoehe(df))


def formular_neue_artikelgruppe() -> None:
    profile = lookup_liste("SELECT Profil FROM Profil_Abk ORDER BY Profil")
    materialien = lookup_liste("SELECT Material FROM Material_Gruppe ORDER BY Material")

    if not profile or not materialien:
        st.warning("Bitte zuerst unter 'Einstellungen' mindestens ein Profil und ein Material anlegen.")
        return

    with st.form("form_neue_gruppe", clear_on_submit=True):
        profil = st.selectbox("Profil", profile)
        mass = st.text_input("Mass")
        material = st.selectbox("Material", materialien)
        _, col_btn = st.columns([3, 1])
        abgeschickt = col_btn.form_submit_button("Anlegen", type="primary", use_container_width=True)
        if abgeschickt:
            try:
                barcode = logic.create_artikel_gruppe(profil, mass, material)
                st.success(f"Neue Artikelgruppe angelegt! Barcode: {barcode}")
            except logic.LagerFehler as e:
                st.error(str(e))


def formular_neue_materialgruppe() -> None:
    with st.form("form_material", clear_on_submit=True):
        material = st.text_input("Material")
        gruppe = st.text_input("Gruppe")
        abk = st.text_input("Abkuerzung (fuer Barcode)")
        _, col_btn = st.columns([3, 1])
        abgeschickt = col_btn.form_submit_button("Anlegen", type="primary", use_container_width=True)
        if abgeschickt and material and gruppe and abk:
            try:
                db.execute(
                    "INSERT INTO Material_Gruppe (Material, Gruppe, Abkuerzung) VALUES (?, ?, ?)",
                    (material, gruppe, abk.upper()),
                )
                st.success("Hinzugefuegt.")
            except db.IntegrityError:
                st.error("Existiert bereits.")


# --------------------------------------------------------------
# Kombinierte Formulare fuer den Dashboard-Schnellzugriff:
# EIN Formular fuer Artikel_Liste + Reste zusammen (kein Auswahlbutton mehr noetig).
# Bei "Hinzufuegen" entscheidet die Laenge automatisch ueber das Ziel.
# --------------------------------------------------------------

def formular_hinzufuegen_dialog() -> None:
    gruppen = db.fetch_df("SELECT Barcode, Bezeichnung FROM Artikel_Gruppe ORDER BY Bezeichnung")
    if gruppen.empty:
        st.warning("Bitte zuerst eine Artikelgruppe anlegen.")
        return

    orte = lookup_liste("SELECT OrtRegal FROM Lager ORDER BY OrtRegal")
    einheiten = lookup_liste("SELECT Symbol FROM Einheit ORDER BY Symbol")

    auswahl = st.selectbox(
        "Artikelgruppe", gruppen["Barcode"] + " – " + gruppen["Bezeichnung"], key="hz_gruppe"
    )
    haupt_barcode = auswahl.split(" – ")[0]
    ort = st.selectbox("Ort/Regal", orte, key="hz_ort") if orte else st.text_input("Ort/Regal", key="hz_ort")
    laenge = st.number_input("Laenge/mm", min_value=0.0, step=1.0, key="hz_laenge")
    menge = st.number_input("Menge/Stueck", min_value=1, step=1, value=1, key="hz_menge")
    e_preis = st.number_input("E-Preis", min_value=0.0, step=0.1, format="%.2f", key="hz_preis")
    e_preis_einheit = (
        st.selectbox("E-Preis pro Einheit", einheiten, key="hz_einheit")
        if einheiten else st.text_input("E-Preis pro Einheit", key="hz_einheit")
    )

    grenze = logic.schrott_grenze_mm()
    auto_ist_rest = 0 < laenge <= grenze
    if laenge > 0:
        if auto_ist_rest:
            st.warning(
                f"Laenge {laenge:.0f} mm ≤ {grenze:.0f} mm → wird automatisch als **Rest** gespeichert."
            )
        else:
            st.info(
                f"Laenge {laenge:.0f} mm > {grenze:.0f} mm → wird als **voller Artikel** gespeichert."
            )

    ueberschreiben = st.checkbox("Automatische Zuordnung manuell aendern", key="hz_override")
    ziel_ist_rest = auto_ist_rest
    if ueberschreiben:
        ziel_label = st.radio(
            "Speichern als", ["Voller Artikel", "Rest"],
            index=1 if auto_ist_rest else 0, key="hz_zielwahl", horizontal=True,
        )
        ziel_ist_rest = ziel_label == "Rest"

    ziel_table = "Reste" if ziel_ist_rest else "Artikel_Liste"
    typ = "Rest" if ziel_ist_rest else "Voll"

    _, col_btn = st.columns([3, 1])
    if col_btn.button("Hinzufuegen", type="primary", key="hz_submit", use_container_width=True):
        try:
            neuer_barcode = logic.add_artikel_stueck(
                ziel_table, haupt_barcode, ort, typ, laenge, int(menge), e_preis, e_preis_einheit
            )
            st.success(f"Als {typ} eingebucht! Stueck-Barcode: {neuer_barcode}")
            for k in ("hz_laenge", "hz_menge", "hz_preis", "hz_override", "hz_zielwahl"):
                st.session_state.pop(k, None)
            st.rerun()
        except logic.LagerFehler as e:
            st.error(str(e))


def _kombinierte_stuecke(spalten: str) -> pd.DataFrame:
    """Artikel_Liste + Reste zusammen, mit einer 'Quelle'-Spalte, die die Herkunftstabelle festhaelt."""
    al = db.fetch_df(f"SELECT {spalten} FROM Artikel_Liste")
    al["Quelle"] = "Artikel_Liste"
    re_df = db.fetch_df(f"SELECT {spalten} FROM Reste")
    re_df["Quelle"] = "Reste"
    return pd.concat([al, re_df], ignore_index=True)


def formular_entnahme_dialog() -> None:
    stuecke = _kombinierte_stuecke("Barcode2, Bezeichnung, LaengeMM, MengeStueck")
    if stuecke.empty:
        st.info("Keine Artikel zum Entnehmen vorhanden.")
        return

    optionen = (
        stuecke["Barcode2"] + " – " + stuecke["Bezeichnung"].fillna("")
        + " (" + stuecke["LaengeMM"].fillna(0).astype(str) + " mm, " + stuecke["Quelle"] + ")"
    )
    auswahl = st.selectbox("Stueck waehlen", optionen, key="ent_auswahl")
    barcode2 = auswahl.split(" – ")[0]

    zeile = stuecke[stuecke["Barcode2"] == barcode2].iloc[0]
    table = zeile["Quelle"]
    initiale_laenge = float(zeile["LaengeMM"] or 0)

    # Eigener Key je Stueck (statt fixer Key) - so zeigen die Felder beim Wechsel der
    # Auswahl garantiert den frischen Wert, ganz ohne session_state manuell zuruecksetzen.
    st.caption(f"Urspruengliche Laenge: {initiale_laenge:.0f} mm ({table.replace('_', ' ')})")
    genutzt = st.number_input(
        "Wie viel wurde abgeschnitten/genutzt (mm)?", min_value=0.0, max_value=initiale_laenge,
        step=1.0, key=f"ent_genutzt_{barcode2}",
    )
    rest = initiale_laenge - genutzt
    st.caption(f"Berechnete Restlaenge: {rest:.0f} mm")

    ist_schrott = False
    if logic.ist_schrott_kandidat(rest):
        ist_schrott = st.checkbox(
            f"Reststueck ist nur {rest:.0f} mm lang – als Schrott/Muell entsorgen "
            "(statt in die Reste-Liste zu legen)?",
            key=f"ent_schrott_{barcode2}",
        )

    _, col_btn = st.columns([3, 1])
    if col_btn.button("Entnehmen", type="primary", key="ent_submit", use_container_width=True):
        try:
            msg = logic.process_material_entnahme(table, barcode2, genutzt, ist_schrott)
            st.success(msg)
            st.rerun()
        except logic.LagerFehler as e:
            st.error(str(e))


def formular_bearbeiten_dialog() -> None:
    stuecke = _kombinierte_stuecke("Barcode2, Bezeichnung, LaengeMM, OrtRegal, MengeStueck, EPreis, EPreisEinheit")
    if stuecke.empty:
        st.info("Keine Artikel vorhanden.")
        return

    barcode2 = st.selectbox("Stueck waehlen", stuecke["Barcode2"], key="be_auswahl")
    zeile = stuecke[stuecke["Barcode2"] == barcode2].iloc[0]
    table = zeile["Quelle"]

    orte = lookup_liste("SELECT OrtRegal FROM Lager ORDER BY OrtRegal")
    einheiten = lookup_liste("SELECT Symbol FROM Einheit ORDER BY Symbol")

    # Eigener Key je Stueck (statt fixer Key) - so zeigen die Felder beim Wechsel der
    # Auswahl garantiert den frischen Wert, ganz ohne session_state manuell zuruecksetzen.
    neue_laenge = st.number_input("Laenge/mm", value=float(zeile["LaengeMM"] or 0), min_value=0.0, key=f"be_laenge_{barcode2}")
    neuer_ort = (
        st.selectbox(
            "Ort/Regal", orte,
            index=orte.index(zeile["OrtRegal"]) if zeile["OrtRegal"] in orte else 0, key=f"be_ort_{barcode2}",
        ) if orte else st.text_input("Ort/Regal", value=zeile["OrtRegal"] or "", key=f"be_ort_{barcode2}")
    )
    neue_menge = st.number_input("Menge/Stueck", value=int(zeile["MengeStueck"] or 1), min_value=1, step=1, key=f"be_menge_{barcode2}")
    neuer_preis = st.number_input("E-Preis", value=float(zeile["EPreis"] or 0), min_value=0.0, format="%.2f", key=f"be_preis_{barcode2}")
    neue_einheit = (
        st.selectbox(
            "E-Preis pro Einheit", einheiten,
            index=einheiten.index(zeile["EPreisEinheit"]) if zeile["EPreisEinheit"] in einheiten else 0, key=f"be_einheit_{barcode2}",
        ) if einheiten else st.text_input("E-Preis pro Einheit", value=zeile["EPreisEinheit"] or "", key=f"be_einheit_{barcode2}")
    )

    confirm_key = f"be_confirm_del_{barcode2}"
    col_del, _, col_save = st.columns([1, 2, 1])
    if col_del.button("Loeschen", key=f"be_del_{barcode2}"):
        st.session_state[confirm_key] = True
    if col_save.button("Speichern", type="primary", key=f"be_save_{barcode2}", use_container_width=True):
        logic.edit_artikel_stueck(
            table, barcode2, LaengeMM=neue_laenge, OrtRegal=neuer_ort,
            MengeStueck=int(neue_menge), EPreis=neuer_preis, EPreisEinheit=neue_einheit,
        )
        st.success("Aenderungen gespeichert.")
        st.rerun()

    if st.session_state.get(confirm_key):
        st.warning(f"'{barcode2}' wirklich loeschen? Das Stueck wandert in den Papierkorb.")
        col_ja, col_abbrechen = st.columns(2)
        if col_ja.button("Ja, loeschen", type="primary", key=f"be_del_ja_{barcode2}", use_container_width=True):
            logic.soft_delete_artikel_stueck(table, barcode2)
            st.session_state.pop(confirm_key, None)
            st.warning(f"Artikel '{barcode2}' in den Papierkorb verschoben.")
            st.rerun()
        if col_abbrechen.button("Abbrechen", key=f"be_del_abbrechen_{barcode2}", use_container_width=True):
            st.session_state.pop(confirm_key, None)
            st.rerun()


# --------------------------------------------------------------
# Dialoge fuer den Dashboard-Schnellzugriff (modale Fenster statt Seitenwechsel)
# --------------------------------------------------------------

@st.dialog("Hinzufuegen", width="medium")
def dialog_hinzufuegen() -> None:
    formular_hinzufuegen_dialog()


@st.dialog("Material entnehmen", width="medium")
def dialog_entnahme() -> None:
    formular_entnahme_dialog()


@st.dialog("Bearbeiten / Loeschen", width="medium")
def dialog_bearbeiten() -> None:
    formular_bearbeiten_dialog()


@st.dialog("Neue Artikelgruppe")
def dialog_artikel_gruppe() -> None:
    formular_neue_artikelgruppe()


@st.dialog("Neue Materialgruppe")
def dialog_material_gruppe() -> None:
    formular_neue_materialgruppe()


# --------------------------------------------------------------
# Filterleiste fuer die Uebersicht einer einzelnen Tabelle (Artikel_Liste
# oder Reste) - anders als die "Erweiterte Filter" im Dashboard nur auf
# diese eine Tabelle bezogen.
# --------------------------------------------------------------

def filter_bar(table: str, key_prefix: str) -> pd.DataFrame | None:
    """Zeigt eine Filterleiste fuer 'table'. Gibt das gefilterte DataFrame zurueck,
    sobald gefiltert wurde - sonst None (dann zeigt die Seite die volle Tabelle)."""
    profil_opt = [""] + lookup_liste("SELECT DISTINCT Profil FROM Artikel_Gruppe ORDER BY Profil")
    material_opt = [""] + lookup_liste("SELECT DISTINCT Material FROM Artikel_Gruppe ORDER BY Material")
    ort_opt = [""] + lookup_liste("SELECT OrtRegal FROM Lager ORDER BY OrtRegal")
    barcode_opt = lookup_liste(f"SELECT DISTINCT Barcode2 FROM {table} ORDER BY Barcode2")
    bezeichnung_opt = lookup_liste(f"SELECT DISTINCT Bezeichnung FROM {table} ORDER BY Bezeichnung")
    mass_opt = lookup_liste(f"SELECT DISTINCT Mass FROM {table} ORDER BY Mass")

    with st.form(f"{key_prefix}_filter_form"):
        c1, c2, c3 = st.columns(3)
        f_profil = c1.selectbox("Profil", profil_opt, key=f"{key_prefix}_f_profil")
        f_material = c2.selectbox("Material", material_opt, key=f"{key_prefix}_f_material")
        f_ort = c3.selectbox("Lagerort", ort_opt, key=f"{key_prefix}_f_ort")

        c4, c5, c6 = st.columns(3)
        f_barcode = c4.selectbox(
            "Barcode", barcode_opt, index=None, accept_new_options=True,
            placeholder="Barcode...", key=f"{key_prefix}_f_barcode",
        )
        f_bezeichnung = c5.selectbox(
            "Bezeichnung", bezeichnung_opt, index=None, accept_new_options=True,
            placeholder="Bezeichnung...", key=f"{key_prefix}_f_bezeichnung",
        )
        f_mass = c6.selectbox(
            "Mass", mass_opt, index=None, accept_new_options=True,
            placeholder="Mass...", key=f"{key_prefix}_f_mass",
        )

        c7, c8 = st.columns(2)
        f_laenge_von = c7.number_input("Laenge von (mm)", min_value=0.0, step=10.0, key=f"{key_prefix}_f_laenge_von")
        f_laenge_bis = c8.number_input("Laenge bis (mm)", min_value=0.0, step=10.0, key=f"{key_prefix}_f_laenge_bis")

        _, col_btn = st.columns([3, 1])
        gefiltert = col_btn.form_submit_button("Filtern", type="primary", use_container_width=True)

    if not gefiltert:
        return None

    ergebnisse = logic.erweiterte_suche(
        profil=f_profil or "", barcode=f_barcode or "", bezeichnung=f_bezeichnung or "",
        ort=f_ort or "", material=f_material or "", mass=f_mass or "",
        laenge_von=f_laenge_von, laenge_bis=f_laenge_bis,
    )
    return ergebnisse.get(table, pd.DataFrame())


# --------------------------------------------------------------
# Seiten
# --------------------------------------------------------------

def page_dashboard() -> None:
    st.title("Dashboard")

    col1, col2, col3 = st.columns(3)
    col1.metric("Artikel (voll)", db.fetch_one("SELECT COUNT(*) c FROM Artikel_Liste")["c"])
    col2.metric("Reststuecke", db.fetch_one("SELECT COUNT(*) c FROM Reste")["c"])
    col3.metric("Artikelgruppen", db.fetch_one("SELECT COUNT(*) c FROM Artikel_Gruppe")["c"])

    st.divider()
    st.subheader("Suche")
    col_nach, col_begriff = st.columns([1, 3])
    nach = col_nach.radio("Suchen nach", ["Barcode", "Bezeichnung"], horizontal=True)

    if nach == "Barcode":
        vorschlaege = sorted(set(logic.distinct_werte("Barcode")) | set(logic.distinct_werte("Barcode2")))
    else:
        vorschlaege = logic.distinct_werte("Bezeichnung")

    begriff = col_begriff.selectbox(
        "Suchbegriff",
        options=vorschlaege,
        index=None,
        accept_new_options=True,
        placeholder="Aus Liste waehlen, tippen oder Barcode scannen...",
    )

    if begriff:
        ergebnisse = logic.suche(begriff, nach)
        for name, df in ergebnisse.items():
            if df.empty:
                st.write(f"**{name}** ({len(df)} Treffer)")
                continue
            col_titel, col_pdf = st.columns([5, 1])
            col_titel.write(f"**{name}** ({len(df)} Treffer)")
            with col_pdf:
                pdf_download_button(df, f"Suche_{name}", key=f"pdf_suche_{name}", label="📄 PDF")
            st.dataframe(df, use_container_width=True, hide_index=True, height=volle_hoehe(df))
            st.caption(f"Summe Laenge x Menge: {(df['LaengeMM'].fillna(0) * df['MengeStueck'].fillna(0)).sum():.0f} mm")

    st.divider()
    st.subheader("Erweiterte Filter")
    with st.form("erweiterte_filter_form"):
        profil_opt = [""] + lookup_liste("SELECT DISTINCT Profil FROM Artikel_Gruppe ORDER BY Profil")
        material_opt = [""] + lookup_liste("SELECT DISTINCT Material FROM Artikel_Gruppe ORDER BY Material")
        ort_opt = [""] + lookup_liste("SELECT OrtRegal FROM Lager ORDER BY OrtRegal")

        c1, c2, c3, c4 = st.columns(4)
        f_profil = c1.selectbox("Profil", profil_opt, key="filter_profil")
        f_material = c2.selectbox("Material", material_opt, key="filter_material")
        f_ort = c3.selectbox("Lagerort", ort_opt, key="filter_ort")
        f_barcode = c4.selectbox(
            "Barcode", options=vorschlaege if nach == "Barcode" else [],
            index=None, accept_new_options=True, placeholder="Barcode...", key="filter_barcode",
        )

        c5, c6, c7, c8 = st.columns(4)
        f_bezeichnung = c5.selectbox(
            "Bezeichnung", options=logic.distinct_werte("Bezeichnung"),
            index=None, accept_new_options=True, placeholder="Bezeichnung...", key="filter_bezeichnung",
        )
        f_mass = c6.selectbox(
            "Mass", options=lookup_liste("SELECT DISTINCT Mass FROM Artikel_Gruppe ORDER BY Mass"),
            index=None, accept_new_options=True, placeholder="Mass...", key="filter_mass",
        )
        f_laenge_von = c7.number_input("Laenge von (mm)", min_value=0.0, step=10.0, key="filter_laenge_von")
        f_laenge_bis = c8.number_input("Laenge bis (mm)", min_value=0.0, step=10.0, key="filter_laenge_bis")

        _, col_btn = st.columns([3, 1])
        gefiltert = col_btn.form_submit_button("Filtern", type="primary", use_container_width=True)

    if gefiltert:
        ergebnisse = logic.erweiterte_suche(
            profil=f_profil or "", barcode=f_barcode or "", bezeichnung=f_bezeichnung or "",
            ort=f_ort or "", material=f_material or "", mass=f_mass or "",
            laenge_von=f_laenge_von, laenge_bis=f_laenge_bis,
        )
        frames = []
        for quelle, df in ergebnisse.items():
            if not df.empty:
                df = df.copy()
                df.insert(0, "Quelle", quelle)
                frames.append(df)
        if frames:
            kombiniert = pd.concat(frames, ignore_index=True)
            col_titel, col_pdf = st.columns([5, 1])
            col_titel.success(f"{len(kombiniert)} Treffer")
            with col_pdf:
                pdf_download_button(kombiniert, "Erweiterte_Filter", key="pdf_erweiterte_filter", label="📄 PDF")
            st.dataframe(kombiniert, use_container_width=True, hide_index=True, height=volle_hoehe(kombiniert))
        else:
            st.info("Keine Treffer fuer diese Filterkombination.")

    st.divider()
    st.subheader("Exportieren")
    st.caption("Entspricht dem Export-Button im alten Excel-Dashboard.")
    ausgewaehlt = st.multiselect(
        "Welche Tabellen exportieren?", logic.EXPORTIERBARE_TABELLEN, default=logic.EXPORTIERBARE_TABELLEN
    )
    if ausgewaehlt:
        zeitstempel = f"{pd.Timestamp.now():%y-%m-%d_%H-%M}"
        col_excel, col_pdf = st.columns(2)
        col_excel.download_button(
            "Als Excel herunterladen",
            data=logic.export_excel_bytes(ausgewaehlt),
            file_name=f"Lager_System_{zeitstempel}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        col_pdf.download_button(
            "Als PDF herunterladen",
            data=logic.export_pdf_bytes(ausgewaehlt),
            file_name=f"Lager_System_{zeitstempel}.pdf",
            mime="application/pdf",
        )

        st.markdown("**Per E-Mail versenden**")
        st.caption(
            "Oeffnet einen vorausgefuellten Entwurf in deinem Standard-Mail-Programm. "
            "Die oben heruntergeladene Datei bitte manuell anhaengen."
        )
        empfaenger = st.text_input("Empfaenger-Email", key="email_empfaenger")
        if empfaenger:
            betreff = logic.hole_email_betreff(ausgewaehlt)
            text = logic.hole_email_text(ausgewaehlt)
            mailto_link = (
                f"mailto:{urllib.parse.quote(empfaenger)}"
                f"?subject={urllib.parse.quote(betreff)}"
                f"&body={urllib.parse.quote(text)}"
            )
            st.link_button("E-Mail-Entwurf oeffnen", mailto_link)


def page_artikel_liste() -> None:
    st.title("Artikel Liste")

    st.subheader("Filter")
    gefiltert = filter_bar("Artikel_Liste", "al")

    st.divider()
    if gefiltert is None:
        zeige_tabelle("Artikel_Liste", "Volle Artikel", order_by="ID DESC")
    elif gefiltert.empty:
        st.subheader("Gefiltertes Ergebnis (0)")
        st.info("Keine Treffer fuer diese Filterkombination.")
    else:
        col_titel, col_pdf = st.columns([5, 1])
        col_titel.subheader(f"Gefiltertes Ergebnis ({len(gefiltert)})")
        with col_pdf:
            st.write("")
            pdf_download_button(gefiltert, "Artikel_Liste_gefiltert", key="pdf_al_gefiltert", label="📄 PDF")
        st.dataframe(gefiltert, use_container_width=True, hide_index=True, height=volle_hoehe(gefiltert))


def page_reste() -> None:
    st.title("Reste")

    st.subheader("Filter")
    gefiltert = filter_bar("Reste", "re")

    st.divider()
    if gefiltert is None:
        zeige_tabelle("Reste", "Reststuecke", order_by="ID DESC")
    elif gefiltert.empty:
        st.subheader("Gefiltertes Ergebnis (0)")
        st.info("Keine Treffer fuer diese Filterkombination.")
    else:
        col_titel, col_pdf = st.columns([5, 1])
        col_titel.subheader(f"Gefiltertes Ergebnis ({len(gefiltert)})")
        with col_pdf:
            st.write("")
            pdf_download_button(gefiltert, "Reste_gefiltert", key="pdf_re_gefiltert", label="📄 PDF")
        st.dataframe(gefiltert, use_container_width=True, hide_index=True, height=volle_hoehe(gefiltert))


def page_verlauf() -> None:
    st.title("Verlauf")
    st.caption("Reine Protokoll-Ansicht - nicht editierbar, wie im urspruenglichen Excel-System.")
    zeige_tabelle("Verlauf", "Alle Buchungen", order_by="ID DESC")


def page_papierkorb() -> None:
    st.title("Papierkorb")
    st.caption("Geloeschte Artikel/Reste - koennen wiederhergestellt oder endgueltig entfernt werden.")

    df = db.fetch_df("SELECT * FROM Papierkorb ORDER BY ID DESC")
    if df.empty:
        st.info("Papierkorb ist leer.")
        return

    for _, zeile in df.iterrows():
        eintrag_id = int(zeile["ID"])
        with st.container(border=True):
            col_info, col_wieder, col_loeschen = st.columns([4, 1, 1])
            col_info.write(
                f"**{zeile['Barcode2']}** – {zeile['Bezeichnung'] or ''} "
                f"({zeile['LaengeMM'] or 0:.0f} mm, {str(zeile['QuellTabelle']).replace('_', ' ')})  \n"
                f"Geloescht am {zeile['GeloeschtAm']}"
            )
            if col_wieder.button("♻️ Wiederherstellen", key=f"pk_wieder_{eintrag_id}", use_container_width=True):
                try:
                    logic.papierkorb_wiederherstellen(eintrag_id)
                    st.success(f"'{zeile['Barcode2']}' wiederhergestellt.")
                    st.rerun()
                except logic.LagerFehler as e:
                    st.error(str(e))

            confirm_key = f"pk_confirm_del_{eintrag_id}"
            if col_loeschen.button("🗑️ Endgueltig loeschen", key=f"pk_del_{eintrag_id}", use_container_width=True):
                st.session_state[confirm_key] = True

            if st.session_state.get(confirm_key):
                st.error(f"'{zeile['Barcode2']}' wirklich UNWIDERRUFLICH loeschen? Das kann nicht rueckgaengig gemacht werden.")
                col_ja, col_abbrechen = st.columns(2)
                if col_ja.button("Ja, endgueltig loeschen", type="primary", key=f"pk_ja_{eintrag_id}", use_container_width=True):
                    logic.papierkorb_endgueltig_loeschen(eintrag_id)
                    st.session_state.pop(confirm_key, None)
                    st.warning(f"'{zeile['Barcode2']}' endgueltig geloescht.")
                    st.rerun()
                if col_abbrechen.button("Abbrechen", key=f"pk_abbrechen_{eintrag_id}", use_container_width=True):
                    st.session_state.pop(confirm_key, None)
                    st.rerun()


def page_artikel_gruppe() -> None:
    st.title("Artikel Gruppe")
    st.subheader("Neue Artikelgruppe anlegen")
    formular_neue_artikelgruppe()
    st.divider()
    zeige_tabelle("Artikel_Gruppe", "Bestehende Artikelgruppen")


def page_einstellungen() -> None:
    st.title("Einstellungen")
    st.caption("Stammdaten fuer Dropdowns in den anderen Seiten - entspricht dem alten Blatt 'Einstellung'.")

    einst_optionen = ["Lager/Orte", "Profil-Kuerzel", "Material-Gruppen", "Einheiten", "Typen", "Schwellenwerte"]
    auswahl = segmented_nav("Bereich", einst_optionen, "einst_subnav")

    if auswahl == "Lager/Orte":
        with st.form("form_lager", clear_on_submit=True):
            ort = st.text_input("Neuer Ort/Regal")
            _, col_btn = st.columns([3, 1])
            if col_btn.form_submit_button("Hinzufuegen", use_container_width=True) and ort:
                try:
                    db.execute("INSERT INTO Lager (OrtRegal) VALUES (?)", (ort,))
                    st.success("Hinzugefuegt.")
                except db.IntegrityError:
                    st.error("Existiert bereits.")
        zeige_tabelle("Lager", "Orte/Regale")

    elif auswahl == "Profil-Kuerzel":
        with st.form("form_profil", clear_on_submit=True):
            col1, col2 = st.columns(2)
            profil = col1.text_input("Profil (voller Name)")
            abk = col2.text_input("Abkuerzung (fuer Barcode)")
            _, col_btn = st.columns([3, 1])
            if col_btn.form_submit_button("Hinzufuegen", use_container_width=True) and profil and abk:
                try:
                    db.execute("INSERT INTO Profil_Abk (Profil, Abkuerzung) VALUES (?, ?)", (profil, abk.upper()))
                    st.success("Hinzugefuegt.")
                except db.IntegrityError:
                    st.error("Existiert bereits.")
        zeige_tabelle("Profil_Abk", "Profile")

    elif auswahl == "Material-Gruppen":
        formular_neue_materialgruppe()
        zeige_tabelle("Material_Gruppe", "Materialien")

    elif auswahl == "Einheiten":
        with st.form("form_einheit", clear_on_submit=True):
            symbol = st.text_input("Neues Einheit-Symbol (z.B. Stk, kg, m)")
            _, col_btn = st.columns([3, 1])
            if col_btn.form_submit_button("Hinzufuegen", use_container_width=True) and symbol:
                try:
                    db.execute("INSERT INTO Einheit (Symbol) VALUES (?)", (symbol,))
                    st.success("Hinzugefuegt.")
                except db.IntegrityError:
                    st.error("Existiert bereits.")
        zeige_tabelle("Einheit", "Einheiten")

    elif auswahl == "Typen":
        with st.form("form_typ", clear_on_submit=True):
            bez = st.text_input("Neuer Typ (z.B. Voll, Rest)")
            _, col_btn = st.columns([3, 1])
            if col_btn.form_submit_button("Hinzufuegen", use_container_width=True) and bez:
                try:
                    db.execute("INSERT INTO Typ (Bezeichnung) VALUES (?)", (bez,))
                    st.success("Hinzugefuegt.")
                except db.IntegrityError:
                    st.error("Existiert bereits.")
        zeige_tabelle("Typ", "Typen")

    elif auswahl == "Schwellenwerte":
        aktuelle_grenze = logic.schrott_grenze_mm()
        with st.form("form_schrott_grenze"):
            st.caption(
                "Eine gemeinsame Laengen-Grenze (mm) fuer zwei Stellen in der App:\n\n"
                "1. **Bei einer Materialentnahme**: liegt die berechnete Restlaenge darunter, "
                "fragt die App nach, ob das Stueck als Schrott entsorgt werden soll (statt es "
                "automatisch in die Reste-Liste zu legen).\n\n"
                "2. **Beim manuellen Hinzufuegen** neuer Ware: liegt die eingegebene Laenge darunter, "
                "wird das Stueck automatisch als Rest statt als voller Artikel gespeichert."
            )
            neue_grenze = st.number_input(
                "Schrott-/Rest-Grenze (mm)", min_value=0, step=50, value=int(aktuelle_grenze),
            )
            _, col_btn = st.columns([3, 1])
            if col_btn.form_submit_button("Speichern", type="primary", use_container_width=True):
                db.setze_konfiguration("SchrottGrenzeMM", int(neue_grenze))
                st.success(f"Grenze auf {int(neue_grenze)} mm gesetzt.")
                st.rerun()
        st.caption(f"Aktuell aktiv: {int(aktuelle_grenze)} mm")


# --------------------------------------------------------------
# Navigation
# --------------------------------------------------------------

SEITEN = {
    "Dashboard": page_dashboard,
    "Artikel Liste": page_artikel_liste,
    "Reste": page_reste,
    "Verlauf": page_verlauf,
    "Papierkorb": page_papierkorb,
    "Artikel Gruppe": page_artikel_gruppe,
    "Einstellungen": page_einstellungen,
}

st.sidebar.title("Lager System")

seiten_namen = list(SEITEN.keys())
auswahl = st.sidebar.radio("Navigation", seiten_namen, key="nav_seite")

st.sidebar.divider()
st.sidebar.subheader("Schnellzugriff")
st.sidebar.caption(f"Automatische Voll/Rest-Zuordnung, Schwelle {logic.schrott_grenze_mm():.0f} mm")
if st.sidebar.button("➕ Hinzufuegen", use_container_width=True, key="sb_hz"):
    dialog_hinzufuegen()
if st.sidebar.button("✂️ Material entnehmen", use_container_width=True, key="sb_ent"):
    dialog_entnahme()
if st.sidebar.button("✏️ Bearbeiten / Loeschen", use_container_width=True, key="sb_be"):
    dialog_bearbeiten()
if st.sidebar.button("🏷️ Artikel Gruppe", use_container_width=True, key="sb_ag"):
    dialog_artikel_gruppe()
if st.sidebar.button("🧱 Material Gruppe", use_container_width=True, key="sb_mg"):
    dialog_material_gruppe()

SEITEN[auswahl]()

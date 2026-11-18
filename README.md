# Lager System

Web-App-Nachfolger des ursprünglichen Excel/VBA-Lagersystems für ein Metall-Lager (Flacheisen, Rundmaterial, Stahlsorten). Verwaltet Stangen in Längen mit Reststück-Logik, Barcodes, Verlaufsprotokoll und Papierkorb.

Technik: Python, [Streamlit](https://streamlit.io) (Oberfläche), SQLite (lokal) oder Postgres (Cloud).

Weitere Anleitungen:

| Datei | Für wen / wofür |
|---|---|
| [ANLEITUNG_CHEF.md](ANLEITUNG_CHEF.md) | Kurzanleitung für den täglichen Gebrauch (nicht technisch) |
| [ANLEITUNG_CLOUD.md](ANLEITUNG_CLOUD.md) | Betrieb in der Cloud (GitHub + Neon + Streamlit Cloud) |
| [windows-setup/ANLEITUNG_WINDOWS.md](windows-setup/ANLEITUNG_WINDOWS.md) | Betrieb auf einem Windows-Rechner |

## Funktionen

**Seiten** (Navigation links): Dashboard · Artikel Liste · Reste · Verlauf · Papierkorb · Artikel Gruppe · Excel-Import · Einstellungen

**Schnellzugriff** (Seitenleiste, von jeder Seite aus):

- **➕ Hinzufügen** – neues Stück einbuchen. Die Länge entscheidet automatisch, ob es ein voller Artikel (`Artikel_Liste`) oder ein Rest (`Reste`) wird (Schwelle einstellbar, Standard 1000 mm).
- **✂️ Material entnehmen** – Stück wird abgeschnitten. Die Restlänge wird berechnet und als Reststück weitergeführt (oder als Schrott entsorgt, wenn sie unter der Schwelle liegt).
- **✏️ Bearbeiten / Löschen** – Länge, Ort, Menge, Preis ändern; Löschen verschiebt ins Papierkorb.
- **📥 Excel-Import** – springt zur Import-Seite (siehe unten).
- **🏷️ Artikel Gruppe / 🧱 Material Gruppe** – neue Sorten anlegen.

**Suche und Export:** Suche nach Barcode (Gruppen- oder Stück-Barcode, auch per Scanner) oder Bezeichnung, erweiterte Filter (Profil, Material, Ort, Maß, Länge von/bis), Export als Excel/PDF, E-Mail-Entwurf per `mailto:` (Anhang manuell). Jede Tabelle hat einen PDF-Download.

### Mehrfach-Auswahl und Löschen

Auf **Artikel Liste** und **Reste** sowie im **Papierkorb** lassen sich Zeilen per Kästchen auswählen (Kopfzeile = alle; am Computer für mehrere Zeilen Strg bzw. Cmd gedrückt halten, Umschalt = Bereich, am Tablet/Handy einfach nacheinander antippen):

- Artikel Liste / Reste: *„N ausgewählte löschen"* verschiebt nach Rückfrage in den Papierkorb. Bei aktivem Filter gibt es zusätzlich *„Alle N angezeigten löschen"*. Der Filter bleibt aktiv, bis man *„Filter zurücksetzen"* klickt.
- Papierkorb: *„N wiederherstellen"* oder *„N endgültig löschen"* (mit Rückfrage). Wiederherstellen überspringt Stücke, deren Stück-Barcode inzwischen neu vergeben wurde, und nennt sie in der Meldung.

Alle Sammel-Aktionen laufen in **einer Transaktion** (ganz oder gar nicht).

### Excel-Import

Seite **Excel-Import** (oder Schnellzugriff-Button): eine vorbereitete Artikelliste als `.xlsx` auf einmal einbuchen. Ablauf: Datei hochladen → Vorschau prüfen → *„Jetzt einbuchen"*.

| Spalte | Pflicht | Beispiel |
|---|---|---|
| Profil | ja | `Flacheisen` |
| Mass | ja | `40x10`, `R20` |
| Material | ja (leer = `---`) | `ST37K` |
| Laenge_mm | ja | `3040` |
| Lagerort | ja | `Saege unten` |
| Menge | nein (Standard 1) | `2` |
| E-Preis | nein (Standard 0) | `1,5` |
| E-Preis-Einheit | nein (Standard `Stk`) | `kg` |

Was das System selbst erledigt:

- **Spalten erkennen:** Reihenfolge und Groß-/Kleinschreibung egal, gängige Synonyme (`Ort`/`Regal`, `Länge`, `Stück` …) werden erkannt, Titelzeilen vor der Kopfzeile sind erlaubt. Leere Vorlage: Button auf der Import-Seite.
- **Schreibweisen vereinheitlichen:** `40 x 10` → `40x10`, `3.250` → 3250, `1,5` → 1.5.
- **Fehlendes anlegen:** unbekannte Artikelgruppen, Profile, Materialien, Lagerorte, Einheiten (Barcode-Kürzel werden automatisch gebildet; neues Material bekommt die Gruppe „Unbekannt").
- **Voll oder Rest** nach der Schwelle (wie beim Hinzufügen); jede Zeile bekommt einen Stück-Barcode und einen Verlauf-Eintrag.
- **Tippfehler-Prüfung:** Ist ein neuer Name (Profil, Material, Lagerort) einem bestehenden sehr ähnlich (Textähnlichkeit ≥ 80 %, z. B. `Flacheisn`), muss vor dem Einbuchen entschieden werden: *Tippfehler → bestehenden Namen nehmen* oder *wirklich neu*. Namen, die sich nur in Ziffern unterscheiden (`Regal 1` / `Regal 2`), gelten nicht als Tippfehler.
- **Doppelt-Schutz:** Stücke, die schon im Lager sind (gleiche Gruppe, Länge und Ort), werden standardmäßig übersprungen.
- **Fehlerhafte Zeilen** (z. B. Länge keine Zahl, Lagerort fehlt) werden mit der Excel-Zeilennummer gemeldet und nie eingebucht.
- **Alles oder nichts:** der Import läuft in einer Transaktion.

Umsetzung: [excel_import.py](excel_import.py) (`analysiere()` = Trockenlauf für die Vorschau, `importiere()` = schreibt).

## Betriebsarten

`db.py` wählt automatisch anhand der Umgebungsvariable bzw. des Streamlit-Secrets `DATABASE_URL`:

- **Nicht gesetzt** (Normalfall auf Mac/Windows): lokale SQLite-Datei `lager.db`.
- **Gesetzt:** Postgres (z. B. Neon) – siehe [ANLEITUNG_CLOUD.md](ANLEITUNG_CLOUD.md).

Der Rest der App (`logic.py`, `excel_import.py`, `app.py`) merkt davon nichts.

## Starten (lokal auf dem Mac)

Die App läuft als **Hintergrunddienst** und startet automatisch, sobald sich dieser Mac einschaltet/anmeldet – normalerweise musst du gar nichts tun.

Falls sie doch mal nicht erreichbar ist: Doppelklick auf `start.command` im Finder.
- Läuft der Dienst noch im Hintergrund, öffnet sich einfach der Browser mit der App.
- Falls nicht, wird er darüber gestartet (dann muss das Terminal-Fenster offen bleiben, bis der Dienst beim nächsten Neustart des Macs wieder automatisch übernimmt).

Adresse: `http://localhost:8501`

Manuell starten geht auch:

```bash
cd ~/Lagersystem
source venv/bin/activate
streamlit run app.py
```

## Hintergrunddienst (automatischer Start/Neustart)

Zwei macOS-LaunchAgents in `~/Library/LaunchAgents/`:

| Agent | Aufgabe |
|---|---|
| `com.lagersystem.streamlit.plist` | Startet `server.sh` beim Anmelden (`RunAtLoad`) und nach einem Absturz neu (`KeepAlive`). Log: `~/Library/Logs/lagersystem.log` |
| `com.lagersystem.backup.plist` | Führt `backup.sh` täglich um 20:00 Uhr aus. Log: `~/Library/Logs/lagersystem-backup.log` |

Nützliche Befehle:

```bash
# Status prüfen (vorn steht die Prozess-ID, wenn der Dienst läuft)
launchctl list | grep lagersystem

# Dienst neu starten (z. B. nach einem Update)
launchctl kickstart -k gui/$(id -u)/com.lagersystem.streamlit

# Dienst stoppen / wieder laden
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.lagersystem.streamlit.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.lagersystem.streamlit.plist
```

## Update einspielen

Der Dienst läuft aus `~/Lagersystem` (ein Git-Klon von `github.com/houcinehassine/lagersystem`), **nicht** aus einem anderen Arbeitsordner. Nach Änderungen im Repo:

```bash
cd ~/Lagersystem && git pull
launchctl kickstart -k gui/$(id -u)/com.lagersystem.streamlit
```

Danach die App im Browser neu laden. `git pull` fasst `lager.db` nicht an (steht in `.gitignore`). Die Streamlit Community Cloud übernimmt einen Push auf `main` automatisch. Neue Python-Pakete (`requirements.txt`) müssten lokal zusätzlich mit `venv/bin/pip install -r requirements.txt` installiert werden.

## Zugriff von anderen Geräten im selben WLAN

Andere Geräte (Tablet, Handy, weiterer PC) im **selben WLAN/Netzwerk** wie der Mac können die App ebenfalls öffnen:

1. Im Log (`~/Library/Logs/lagersystem.log`) nach der Zeile **"Network URL"** schauen, z. B.:
   ```
   Network URL: http://192.168.142.86:8501
   ```
2. Diese Adresse auf dem anderen Gerät in einem Browser öffnen.

Falls die Seite nicht lädt: macOS fragt beim allerersten Start evtl. "Eingehende Netzwerkverbindungen zulassen?" – das muss bestätigt werden (Systemeinstellungen → Netzwerk → Firewall, falls die Frage verpasst wurde).

**Hinweis:** Die Adresse ändert sich, wenn der Mac in einem anderen Netzwerk hängt (z. B. VPN/Hotspot), und die lokale Variante funktioniert nur im selben Netzwerk. Für Zugriff von überall gibt es die Cloud-Variante ([ANLEITUNG_CLOUD.md](ANLEITUNG_CLOUD.md)). Die lokale App hat keinen Login.

## Mehrbenutzerbetrieb

Mehrere Personen können gleichzeitig lesen und schreiben:

- Die lokale Datenbank läuft im SQLite-**WAL-Modus**, dadurch blockieren sich lesende und schreibende Zugriffe nicht gegenseitig.
- Barcode-Vergabe, Entnahme und alle Sammel-Aktionen sind über einen internen Lock (`_SCHREIB_LOCK` in `logic.py`) abgesichert, damit zwei Nutzer nicht gleichzeitig denselben Barcode erzeugen können. Der Lock gilt innerhalb **eines** Streamlit-Prozesses.
- Bei sehr vielen gleichzeitigen Schreibzugriffen wartet die App bis zu 5 Sekunden, statt sofort einen Fehler zu zeigen.

Getestet mit 100 gleichzeitigen Schreibzugriffen (5 parallele "Nutzer") ohne Konflikte oder doppelte Barcodes.

## Projektstruktur

| Datei | Zweck |
|---|---|
| `app.py` | Streamlit-Oberfläche (alle Seiten und Dialoge) |
| `logic.py` | Geschäftslogik (Barcode-Generierung, Entnahme, Papierkorb, Suche, Export) |
| `excel_import.py` | Excel-Import: Spaltenerkennung, Prüfung, Tippfehler-Erkennung, Einbuchen in einer Transaktion |
| `db.py` | Datenzugriffsschicht (SQLite lokal / Postgres in der Cloud), `transaktion()` für atomare Abläufe |
| `schema.sql` / `schema_postgres.sql` | Datenbankschema (SQLite / Postgres, inhaltlich identisch) |
| `migrate_sqlite_to_postgres.py` | Einmalige Übertragung der lokalen Daten in die Cloud-Datenbank |
| `lager.db` | Die lokale Datenbank (nicht im Git) |
| `backup.sh` | Backup-Script (Start und täglich 20:00) |
| `server.sh` | Start-Script für den Hintergrunddienst (LaunchAgent) |
| `start.command` | Doppelklick-Starter für den Finder (manueller Fallback) |
| `windows-setup/` | Windows-Pendants (Start, Backup, Anleitung) |
| `.streamlit/secrets.toml.example` | Vorlage für die Cloud-Zugangsdaten |

## Datenmodell

- **Stammdaten:** `Lager` (Orte), `Typ`, `Einheit`, `Konfiguration` (Schlüssel/Wert, z. B. `SchrottGrenzeMM`), `Profil_Abk`, `Material_Gruppe`
- **`Artikel_Gruppe`:** Artikeltyp mit Haupt-Barcode, z. B. `FLS370001` (Profil-Kürzel + Material-Kürzel + 4-stellige Nummer). Bezeichnung = `Profil-Mass-Material`.
- **`Artikel_Liste`** (volle Stücke) und **`Reste`**: gleich aufgebaut; `Barcode2` ist der Stück-Barcode, z. B. `FLS370001-2`.
- **`Verlauf`:** Buchungsprotokoll (Länge negativ = Verbrauch; Typ Voll/Rest/Verbrauch).
- **`Papierkorb`:** gelöschte Stücke mit `QuellTabelle` und Löschzeitpunkt.

## Backup

`backup.sh` legt eine Kopie der Datenbank in `backups/lager_JJJJ-MM-TT.db` an (eine pro Tag, überschreibt sich bei mehreren Läufen am selben Tag). Es werden die letzten 30 Tage aufgehoben, ältere Backups werden gelöscht. Es läuft bei jedem Start der App und täglich um 20:00 Uhr.

Manuelles Backup jederzeit möglich:

```bash
cd ~/Lagersystem
./backup.sh
```

In der Cloud-Variante übernimmt Neon die Sicherung (siehe [ANLEITUNG_CLOUD.md](ANLEITUNG_CLOUD.md)).

## Bekannte Einschränkungen

Stand der Code-Analyse; nichts davon ist ein akuter Fehler, aber gut zu wissen:

- **Stück-Barcode nur pro Tabelle eindeutig:** `Artikel_Liste` und `Reste` zählen ihre Stücknummern getrennt, `FLS370010-1` kann also in beiden vorkommen. Die kombinierten Auswahllisten bei Entnahme und Bearbeiten nehmen bei einer Kollision den ersten Treffer. Nach dem Löschen des höchsten Stücks wird dessen Nummer neu vergeben.
- **Schwelle uneinheitlich:** Beim Hinzufügen und Import gilt `Länge ≤ Schwelle` als Rest, bei der Entnahme `Restlänge < Schwelle`.
- **Rest mit Typ „Rest" in `Artikel_Liste`:** Eine Restlänge ≥ Schwelle geht zurück in `Artikel_Liste`, behält aber den Typ „Rest".
- **Verlauf ist unvollständig:** Bearbeiten, Löschen und Wiederherstellen schreiben keinen Verlauf-Eintrag, und es wird kein Benutzer protokolliert.
- **Entnahme nicht atomar:** Sie besteht aus mehreren Einzel-Commits (Import und Sammel-Aktionen nutzen dagegen eine Transaktion).
- **Stammdaten nicht löschbar:** Artikelgruppen, Profile, Materialien, Lagerorte und Verlauf lassen sich in der App nicht entfernen, nur anlegen.
- **Postgres-Performance:** `init_db()` läuft bei jedem Seitenlauf und jede Abfrage öffnet eine eigene Verbindung (kein Pooling).
- **Kein Login** in der lokalen Variante; in der Cloud schützt die Streamlit-Freigabe per E-Mail-Einladung.

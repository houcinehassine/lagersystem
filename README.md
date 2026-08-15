# Lager System

Web-App-Nachfolger des ursprünglichen Excel/VBA-Lagersystems. Läuft lokal auf diesem Mac (`~/Lagersystem`), mehrere Personen im selben Netzwerk können gleichzeitig darauf zugreifen.

## Starten

Die App läuft als **Hintergrunddienst** und startet automatisch, sobald sich dieser Mac einschaltet/anmeldet – normalerweise musst du gar nichts tun.

Falls sie doch mal nicht erreichbar ist: Doppelklick auf `start.command` im Finder.
- Läuft der Dienst noch im Hintergrund, öffnet sich einfach der Browser mit der App.
- Falls nicht, wird er darüber gestartet (dann muss das Terminal-Fenster offen bleiben, bis der Dienst beim naechsten Neustart des Macs wieder automatisch übernimmt).

Adresse: `http://localhost:8501`

Manuell starten geht auch:

```bash
cd ~/Lagersystem
source venv/bin/activate
streamlit run app.py
```

## Hintergrunddienst (automatischer Start/Neustart)

Eingerichtet über einen macOS LaunchAgent (`~/Library/LaunchAgents/com.lagersystem.streamlit.plist`):

- Startet automatisch, wenn sich dieser Nutzer-Account am Mac anmeldet.
- Startet sich bei einem Absturz automatisch neu (`KeepAlive`).
- Logs: `~/Library/Logs/lagersystem.log`

Nützliche Befehle:

```bash
# Status pruefen
launchctl list | grep lagersystem

# Dienst manuell stoppen
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.lagersystem.streamlit.plist

# Dienst manuell (neu) starten
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.lagersystem.streamlit.plist
```

## Zugriff von anderen Geräten im selben WLAN

Andere Geräte (Tablet, Handy, weiterer PC) im **selben WLAN/Netzwerk** wie der Mac können die App ebenfalls öffnen:

1. Im Log (`~/Library/Logs/lagersystem.log`) nach der Zeile **"Network URL"** schauen, z. B.:
   ```
   Network URL: http://192.168.142.86:8501
   ```
2. Diese Adresse auf dem anderen Gerät in einem Browser öffnen.

Falls die Seite nicht lädt: macOS fragt beim allerersten Start evtl. "Eingehende Netzwerkverbindungen zulassen?" – das muss bestätigt werden (Systemeinstellungen → Netzwerk → Firewall, falls die Frage verpasst wurde).

**Hinweis:** Diese Lösung funktioniert nur innerhalb desselben lokalen Netzwerks (z. B. Büro-WLAN). Für Zugriff von unterwegs/Internet wäre echtes Server-Hosting nötig – das ist bewusst (noch) nicht eingerichtet.

## Mehrbenutzerbetrieb

Mehrere Personen können gleichzeitig lesen und schreiben:

- Die Datenbank läuft im SQLite-**WAL-Modus**, dadurch blockieren sich lesende und schreibende Zugriffe nicht gegenseitig.
- Barcode-Vergabe (Artikelgruppen, Artikel-Stücke, Reststücke) ist über einen internen Lock abgesichert, damit zwei Nutzer nicht gleichzeitig denselben Barcode erzeugen können.
- Bei sehr vielen gleichzeitigen Schreibzugriffen wartet die App bis zu 5 Sekunden, statt sofort einen Fehler zu zeigen.

Getestet mit 100 gleichzeitigen Schreibzugriffen (5 parallele "Nutzer") ohne Konflikte oder doppelte Barcodes.

## Projektstruktur

| Datei | Zweck |
|---|---|
| `app.py` | Streamlit-Oberfläche (alle Seiten) |
| `logic.py` | Geschäftslogik (Barcode-Generierung, Entnahme-Logik, Export) |
| `db.py` | SQLite-Datenzugriffsschicht |
| `schema.sql` | Datenbankschema |
| `lager.db` | Die eigentliche Datenbank |
| `backup.sh` | Taegliches Backup-Script (wird bei jedem Start automatisch ausgefuehrt) |
| `server.sh` | Start-Script fuer den Hintergrunddienst (LaunchAgent) |
| `start.command` | Doppelklick-Starter fuer den Finder (manueller Fallback) |

## Backup

Bei **jedem Start** der App (egal ob automatisch ueber den Hintergrunddienst oder manuell ueber `start.command`) legt `backup.sh` automatisch eine Kopie der Datenbank in `backups/lager_JJJJ-MM-TT.db` an (eine pro Tag, ueberschreibt sich bei mehreren Starts am selben Tag). Es werden automatisch nur die letzten 30 Tage aufgehoben, aeltere Backups werden geloescht.

Manuelles Backup jederzeit moeglich:

```bash
cd ~/Lagersystem
./backup.sh
```

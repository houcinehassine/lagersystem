# Lager System auf einem Windows-PC einrichten

Diese Anleitung verlegt das Lager System vom Mac auf einen Windows-PC (z. B. den PC
deines Chefs), damit es **nicht mehr von einer einzelnen Person abhängt**. Danach
läuft es dort dauerhaft im Hintergrund, startet automatisch beim Hochfahren und
startet sich bei einem Absturz von selbst neu - genau wie aktuell auf dem Mac.

Rechne für die komplette Einrichtung mit ca. 30-45 Minuten.

---

## 1. Python installieren

1. https://www.python.org/downloads/windows/ öffnen, aktuelle Version herunterladen
   (mind. Python 3.10).
2. Installer starten. **Wichtig:** Unten im ersten Fenster das Kästchen
   **"Add python.exe to PATH"** anhaken, bevor auf "Install Now" geklickt wird.
3. Prüfen: Eingabeaufforderung (cmd) öffnen, `python --version` eingeben - es sollte
   eine Versionsnummer erscheinen (z. B. `Python 3.12.4`).

## 2. Projektordner kopieren

1. Auf dem Windows-PC einen Ordner anlegen, z. B. `C:\Lagersystem`.
2. Vom Mac folgende Dateien/Ordner dort hineinkopieren (per USB-Stick, E-Mail an
   dich selbst, gemeinsames Netzlaufwerk o. ä. - **nicht** per iCloud/Cloud-Ordner):
   - `app.py`, `logic.py`, `db.py`, `schema.sql`, `requirements.txt`
   - Der komplette Ordner `windows-setup` (die Dateien darin auf die oberste Ebene
     von `C:\Lagersystem` legen, siehe Schritt 3)
   - **`lager.db`** (die aktuelle Datenbank) - das erst **ganz am Schluss**, direkt
     bevor umgestellt wird (siehe Schritt 8), damit nichts Aktuelles verloren geht.
3. Die Dateien aus `windows-setup` (`backup.py`, `start_server.bat`, `start.bat`,
   `start_hidden.vbs`) direkt in `C:\Lagersystem` legen (nicht im Unterordner
   lassen).

Am Ende sollte `C:\Lagersystem` u. a. enthalten:
`app.py`, `logic.py`, `db.py`, `schema.sql`, `requirements.txt`, `backup.py`,
`start_server.bat`, `start.bat`, `start_hidden.vbs`, `lager.db`.

## 3. Virtuelle Umgebung einrichten

Eingabeaufforderung (cmd) öffnen:

```bat
cd C:\Lagersystem
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

Das dauert ein paar Minuten (lädt Streamlit, Pandas etc. herunter).

## 4. Einmal testen

```bat
venv\Scripts\streamlit.exe run app.py
```

Es sollte sich der Browser öffnen mit der App. Windows fragt beim ersten Start
eventuell **"Windows Defender Firewall hat einige Funktionen blockiert"** - dort
**"Zugriff zulassen"** klicken (sonst können andere Geräte im Netzwerk nicht
zugreifen). Danach das Fenster mit `Strg+C` beenden.

## 5. Automatischen Hintergrunddienst einrichten (Aufgabenplanung)

1. Windows-Suche → **"Aufgabenplanung"** (Task Scheduler) öffnen.
2. Rechts auf **"Aufgabe erstellen..."** (nicht "Einfache Aufgabe").
3. Reiter **Allgemein**:
   - Name: `Lager System`
   - **"Unabhängig von der Benutzeranmeldung ausführen"** NICHT nötig - Standard
     (nur bei angemeldetem Benutzer) reicht.
4. Reiter **Trigger** → "Neu...":
   - **Aufgabe starten:** "Bei Anmeldung"
   - OK.
5. Reiter **Aktionen** → "Neu...":
   - Aktion: "Programm starten"
   - Programm/Skript: `wscript.exe`
   - Argumente hinzufügen: `"C:\Lagersystem\start_hidden.vbs"`
   - OK.
6. Reiter **Bedingungen**: Häkchen bei "Nur starten, falls Computer im
   Netzbetrieb ist" entfernen (falls vorhanden), damit es auch im Akkubetrieb läuft
   (bei einem Laptop).
7. Reiter **Einstellungen**:
   - Häkchen bei **"Fehlgeschlagenen Start der Aufgabe neu starten alle:"**
     setzen → `1 Minute`
   - **"Neustartversuche:"** → `999` (praktisch unbegrenzt)
   - OK, ggf. Windows-Passwort eingeben.

Ab jetzt startet die App automatisch bei jeder Anmeldung an diesem PC und startet
sich bei einem Absturz selbst neu.

**Zum Testen sofort starten**, ohne den PC neu zu starten: die neue Aufgabe
in der Liste der Aufgabenplanung rechtsklicken → **"Ausführen"**.

## 6. Prüfen, ob es läuft

Ca. 10 Sekunden warten, dann im Browser `http://localhost:8501` öffnen - die App
sollte erscheinen. Falls nicht: Datei `C:\Lagersystem\lagersystem.log` öffnen (mit
Editor) und nach Fehlermeldungen schauen.

## 7. IP-Adresse für andere Geräte herausfinden

In der Eingabeaufforderung:

```bat
ipconfig
```

Bei "IPv4-Adresse" nachschauen, z. B. `192.168.1.42`. Andere Geräte im selben
WLAN/Netzwerk (Windows, iOS, Android) erreichen die App dann über:

```
http://192.168.1.42:8501
```

**Empfehlung:** Diesem PC im Router eine feste IP-Adresse zuweisen (DHCP-Reservierung),
damit sich diese Adresse nicht von selbst ändert. Das macht man im
Router-Verwaltungsmenü (meist `192.168.1.1` oder `192.168.0.1` im Browser) - falls
dabei Hilfe gebraucht wird, gerne melden.

## 8. Umstellung: aktuelle Daten übernehmen

Das ist der einzige Schritt, bei dem Timing wichtig ist:

1. Auf dem **Mac** die App kurz nicht benutzen (niemand bucht gerade etwas).
2. Die aktuelle Datei `lager.db` vom Mac (`~/Lagersystem/lager.db`) auf den
   Windows-PC nach `C:\Lagersystem\lager.db` kopieren (überschreibt die leere
   Datenbank von Schritt 4).
3. Aufgabenplanung → Aufgabe "Lager System" → Rechtsklick → "Ausführen" (falls noch
   nicht automatisch gestartet).
4. Auf dem Mac den Hintergrunddienst stoppen, damit nicht zwei Systeme
   gleichzeitig mit unterschiedlichem Stand laufen:
   ```bash
   launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.lagersystem.streamlit.plist
   ```
5. Alle Verknüpfungen/Lesezeichen (siehe Ordner `verknuepfungen`) auf die neue
   Windows-Adresse aus Schritt 7 anpassen und neu verteilen.

Fertig - das Lager System läuft jetzt unabhängig von jeder einzelnen Person.

---

## Kurzübersicht der Dateien

| Datei | Zweck |
|---|---|
| `backup.py` | Tägliches automatisches Backup (letzte 30 Tage) |
| `start_server.bat` | Wird vom Hintergrunddienst aufgerufen (Backup + App-Start) |
| `start_hidden.vbs` | Startet `start_server.bat` ohne sichtbares Fenster |
| `start.bat` | Manueller Doppelklick-Start (Fallback) |
| `lagersystem.log` | Log-Datei, entsteht beim ersten Start |

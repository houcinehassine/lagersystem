# Lager System in der Cloud betreiben (GitHub + Neon + Streamlit Cloud)

Diese Anleitung macht das Lager System von **überall** erreichbar (nicht nur im
Büro-WLAN), über einen privaten Link, den nur eingeladene Personen sehen.
Alle drei genutzten Dienste sind in der kostenlosen Stufe ausreichend.

Rechne mit ca. 30-60 Minuten für die komplette Einrichtung.

---

## Überblick: was wo läuft

- **GitHub** – speichert den Programmcode (keine echten Lagerdaten drin).
- **Neon** – die eigentliche Datenbank in der Cloud (ersetzt die lokale `lager.db`-Datei).
- **Streamlit Community Cloud** – führt die App aus und stellt den Link bereit.

## 1. Neon-Account und Datenbank anlegen

1. https://neon.tech öffnen, **"Sign up"** (kostenlos, z. B. mit GitHub-Account anmelden).
2. Ein neues Projekt anlegen, z. B. Name `lagersystem`.
3. Im Projekt-Dashboard auf **"Connection string"** / **"Connect"** klicken.
4. Die angezeigte Verbindung kopieren - sieht so aus:
   ```
   postgresql://benutzer:passwort@ep-xxxx.eu-central-1.aws.neon.tech/lagersystem?sslmode=require
   ```
   Das ist die `DATABASE_URL` - wird gleich gebraucht. **Sicher aufbewahren**,
   nicht öffentlich teilen (das ist quasi das Passwort zur Datenbank).

## 2. GitHub-Repository anlegen

1. https://github.com öffnen, Account anlegen falls noch keiner vorhanden.
2. Oben rechts **"+"** → **"New repository"**.
3. Name z. B. `lagersystem`, Sichtbarkeit auf **"Private"** stellen (empfohlen -
   auch wenn keine Geheimnisse im Code sind, muss niemand sonst mitlesen).
4. **Kein** Häkchen bei "Add a README" (haben wir schon lokal).
5. **"Create repository"**.

Danach auf der nächsten Seite die angezeigte Repo-Adresse kopieren (Format
`https://github.com/DEIN-NAME/lagersystem.git`).

### Code hochladen

Im Terminal, im Projektordner (`~/Lagersystem` auf diesem Mac):

```bash
git remote add origin https://github.com/DEIN-NAME/lagersystem.git
git branch -M main
git push -u origin main
```

Beim ersten Push fragt Git nach Anmeldedaten - dafür am besten die
[GitHub CLI](https://cli.github.com) nutzen (`gh auth login`) oder ein
[Personal Access Token](https://github.com/settings/tokens) als Passwort
verwenden (GitHub akzeptiert seit einiger Zeit kein normales Passwort mehr
für Git-Operationen).

**Hinweis:** Der Code ist bereits vorbereitet - `.gitignore` sorgt dafür,
dass `lager.db` (die echten Daten), die `venv`-Umgebung und lokale
Geheimnisse **nicht** mit hochgeladen werden.

## 3. Streamlit Community Cloud

1. https://share.streamlit.io öffnen, mit dem **GitHub-Account anmelden**
   (dieselbe Anmeldung wie gerade eben - dadurch bekommt Streamlit Zugriff
   auf das Repo).
2. **"New app"**.
3. Repository `lagersystem`, Branch `main`, Main file path: `app.py` auswählen.
4. **Vor** dem Deployen: unten bei **"Advanced settings"** → **"Secrets"**
   folgendes eintragen (die eigene Neon-Verbindung aus Schritt 1 einsetzen):
   ```toml
   DATABASE_URL = "postgresql://benutzer:passwort@ep-xxxx.neon.tech/lagersystem?sslmode=require"
   ```
5. **"Deploy"** klicken. Dauert 1-2 Minuten beim ersten Mal.

## 4. App privat machen (nur eingeladene Personen)

1. In der App oben rechts auf die drei Punkte → **"Settings"**.
2. Reiter **"Sharing"**.
3. Von "Public" auf **"Only specific people can view this app"** umstellen.
4. E-Mail-Adressen der Kollegen (und deines Chefs) eintragen - die
   bekommen eine Einladung und können sich mit dieser E-Mail-Adresse
   (Google- oder E-Mail-Login) einloggen.

Der Link (`https://DEIN-APP-NAME.streamlit.app`) funktioniert danach von
jedem Gerät (Windows, Mac, iOS, Android) - ganz ohne Installation, aber nur
für eingeladene Personen.

## 5. Echte Daten übertragen (einmalig)

Die Cloud-Datenbank startet leer. Um die aktuellen 86 Artikel + 50
Artikelgruppen (oder den dann aktuellen Stand) zu übertragen:

```bash
cd ~/Lagersystem
export DATABASE_URL="postgresql://benutzer:passwort@ep-xxxx.neon.tech/lagersystem?sslmode=require"
venv/bin/python migrate_sqlite_to_postgres.py
```

Das Script kann gefahrlos mehrfach laufen (überschreibt die Zieltabellen
jedes Mal sauber mit dem aktuellen Stand aus `lager.db`) - praktisch, falls
zwischendurch nochmal ein aktuellerer Stand übertragen werden soll, bevor
die Cloud-Version zur Hauptversion wird.

**Wichtig:** Sobald die Cloud-App produktiv genutzt wird, ist **sie** die
Wahrheit, nicht mehr die lokale `lager.db` - das Script danach nicht mehr
laufen lassen (würde sonst neuere Cloud-Daten wieder überschreiben).

## 6. Testen

Link öffnen, mit einer der eingeladenen E-Mail-Adressen einloggen, prüfen ob
die 86 Artikel da sind, testweise etwas hinzufügen, Seite neu laden - die
Daten müssen erhalten bleiben (das ist der Unterschied zur reinen
GitHub-Cloud-Variante ohne Neon, wo alles bei jedem Neustart verloren ginge).

---

## Kosten & Grenzen (kostenlose Stufen, Stand heute)

- **Neon Free**: 0,5 GB Speicher pro Projekt (weit mehr als genug für dieses
  Lager). Nach ca. 5 Minuten Inaktivität pausiert die Datenbank automatisch
  und wacht bei der naechsten Anfrage in Bruchteilen einer Sekunde wieder auf
  - im normalen Betrieb kaum spuerbar.
- **Streamlit Community Cloud**: kostenlos für private Apps mit
  eingeschränkter Nutzerzahl, App schläft nach Inaktivität ein (wacht beim
  Öffnen automatisch wieder auf).
- **GitHub**: privates Repository kostenlos.

## Automatische Backups

Anders als bei der lokalen SQLite-Lösung übernimmt **Neon automatisch**
Backups/Point-in-Time-Recovery (im kostenlosen Free-Plan für die letzten 6
Stunden, bei den bezahlten Stufen laenger) - das eigene
`backup.sh`/`backup.py`-Script wird für die Cloud-Variante nicht gebraucht.

Quellen zu den aktuellen Neon-Free-Plan-Grenzen: [Neon plans (offizielle Doku)](https://neon.com/docs/introduction/plans), [Neon Free Tier FAQ](https://neon.com/faqs/managed-postgres-databases-free-tier)

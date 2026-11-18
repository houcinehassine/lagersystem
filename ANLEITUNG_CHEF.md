# Lager System – Kurzanleitung

Diese Anleitung zeigt die wichtigsten Handgriffe für die tägliche Arbeit mit dem neuen Lagersystem.

## Öffnen

Im Browser (Safari, Chrome o.ä.) folgende Adresse eingeben – am besten als Lesezeichen speichern:

```
http://192.168.142.86:8501
```

Funktioniert von jedem Gerät (PC, Tablet, Handy), solange es im selben WLAN ist. Die App läuft automatisch im Hintergrund – ein Start ist normalerweise nicht nötig.

## Die Seiten im Überblick

| Seite | Wofür |
|---|---|
| **Dashboard** | Übersicht, Suche, Filter, Export |
| **Artikel Liste** | Alle vollen Artikel |
| **Reste** | Alle Reststücke |
| **Verlauf** | Protokoll aller Buchungen (nur zum Nachschauen) |
| **Papierkorb** | Aus Versehen gelöschte Artikel – siehe unten |
| **Artikel Gruppe** | Neue Artikelsorten anlegen |
| **Einstellungen** | Grunddaten wie Lagerorte, Profile, Materialien |

## Die wichtigsten Aktionen

Links in der Seitenleiste unter **„Schnellzugriff"** – funktionieren von jeder Seite aus:

- **➕ Hinzufügen** – neue Ware einbuchen (Länge entscheidet automatisch, ob es ein voller Artikel oder ein Rest wird)
- **✂️ Material entnehmen** – ein Stück wird abgeschnitten/verbraucht, der Rest wird automatisch weitergeführt
- **✏️ Bearbeiten / Löschen** – Menge, Länge, Lagerort o.ä. korrigieren oder einen Artikel entfernen
- **🏷️ Artikel Gruppe** / **🧱 Material Gruppe** – neue Sorten anlegen, falls etwas komplett Neues ins Lager kommt

Jeder dieser Buttons öffnet ein kleines Fenster mit den passenden Eingabefeldern.

## Viele Artikel auf einmal einbuchen (Excel-Import)

Seitenleiste → **📥 Excel-Import**:

1. **Leere Excel-Vorlage herunterladen** und ausfüllen – pro Zeile ein Stück: *Profil, Mass, Material, Laenge_mm, Lagerort* (optional: *Menge, E-Preis, E-Preis-Einheit*).
2. Datei hochladen. Das System erkennt alles selbst und zeigt eine **Vorschau**: was eingebucht wird, was neu angelegt wird (neue Artikelgruppen, Profile, Materialien, Lagerorte) und welche Zeilen Fehler haben.
3. **„Jetzt einbuchen"** klicken. Es wird entweder alles eingebucht oder – bei einem Problem – gar nichts.

**Tippfehler-Warnung:** Sieht ein neuer Name (Profil, Material oder Lagerort) einem bestehenden sehr ähnlich, z. B. „Flacheisn" statt „Flacheisen", fragt das System nach: *Tippfehler – den bestehenden Namen verwenden* oder *Nein, ist wirklich neu*. Solange nicht jede Rückfrage beantwortet ist, kann nicht eingebucht werden.

Gut zu wissen: Ob ein Stück „Voll" oder „Rest" ist, entscheidet automatisch die Länge (wie beim normalen Hinzufügen). Stücke, die schon im Lager sind (gleicher Artikel, gleiche Länge, gleicher Lagerort), werden standardmäßig übersprungen – so kann dieselbe Liste nicht versehentlich doppelt eingebucht werden.

## Suchen

Auf dem Dashboard: Barcode scannen oder Bezeichnung eingeben – die Ergebnisse erscheinen direkt darunter. Für genauere Suche (z. B. nach Material oder Länge) den Bereich **„Erweiterte Filter"** benutzen.

## Mehrere Artikel auf einmal löschen

Auf den Seiten **Artikel Liste** und **Reste**: links in der Tabelle die Zeile anklicken. **Für mehrere Zeilen am Computer die Strg-Taste (Windows) bzw. Cmd-Taste (Mac) gedrückt halten** und weitere Zeilen anklicken (Umschalt-Taste = ganzer Bereich); das Kästchen in der Kopfzeile wählt alle. Am Tablet/Handy genügt es, die Kästchen nacheinander anzutippen und auf **„🗑️ … ausgewählte löschen"** klicken. Nach einer Rückfrage landen die Stücke im **Papierkorb**.

Das funktioniert auch mit dem Filter: erst filtern, dann entweder einzelne Zeilen auswählen oder – bei aktivem Filter – **„Alle … angezeigten löschen"** nehmen. Der Filter bleibt aktiv, bis man auf „Filter zurücksetzen" klickt.

## Aus Versehen gelöscht?

Kein Problem: Gelöschte Artikel landen zunächst im **Papierkorb**. Dort die Zeilen auswählen (wie oben beschrieben; Kopfzeile = alle) und auf **„♻️ … wiederherstellen"** klicken, um sie zurückzuholen. Erst **„🗑️ … endgültig löschen"** mit extra Rückfrage entfernt sie wirklich. Beides geht für mehrere Artikel gleichzeitig.

Wiederherstellen klappt nur, wenn der Stück-Barcode nicht inzwischen neu vergeben wurde. Solche Stücke bleiben im Papierkorb, und die App nennt sie in der Meldung.

## Bei Problemen

Die App sichert sich täglich selbst ab (automatisches Backup) und startet sich bei einem Absturz von selbst neu. Falls trotzdem mal etwas nicht funktioniert, bitte kurz melden.

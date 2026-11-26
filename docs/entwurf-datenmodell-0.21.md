# Entwurf: Datenmodell für Organisationen, Rollen und Einsätze

Stand: 26.11.2026, überarbeitet nach erster Abstimmung · Zur Abstimmung · gilt ab Version 0.21 (Organisation) und
0.22 (Einsätze)

Dieses Dokument beschreibt, wie Open BOS künftig Landkreis, Feuerwehren,
Personen, Rollen und Einsätze abbildet. Es ist bewusst ohne Programmierdetails
geschrieben, damit es mit Wehrführungen und Kreisebene abgestimmt werden kann.
Die offenen Fragen am Ende sind die wichtigsten Punkte für die Abstimmung.

---

## 1. Ziele

1. **Ein gemeinsamer Server für den Landkreis.** Jede Wehr arbeitet in ihrem
   eigenen Bereich und sieht nur ihre eigenen Drohnen, Aufnahmen und Einsätze.
2. **Kreisebene mit Überblick.** Ausgewählte Personen (z. B. Kreisbrandmeister,
   Kreisausbildung) sehen und verwalten wehrübergreifend.
3. **Zusammenarbeit im Einsatz.** Mehrere Wehren können an einem Einsatz
   beteiligt sein und sehen dann genau diesen Einsatz – nicht mehr.
4. **Saubere Dokumentation.** Wer hatte in welchem Einsatz welche Funktion,
   welche Aufnahmen gehören dazu, wie war das Wetter.
5. **Übernahme ohne Bruch.** Bestehende Konten, Quellen und Gastlinks werden
   beim Update automatisch übernommen.

---

## 2. Datenbank

- **SQLite** als Datei auf dem Server (`config/open-bos.db`), im WAL-Modus
  für gleichzeitiges Lesen. Kein zusätzlicher Dienst, Sicherung als Datei.
- Zugriff über **SQLAlchemy**, Änderungen am Datenmodell über **Alembic**:
  `update.sh` bringt die Datenbank automatisch auf den neuen Stand.
- Ein späterer Wechsel zu **PostgreSQL** bleibt möglich (Einstellung plus
  Datenübernahme), falls der Landkreis z. B. zwei Server für Ausfallsicherheit
  betreiben möchte.
- Technische Einstellungen (Streaming, Karten, Wetter) bleiben in
  `stream.yaml`. In die Datenbank kommen Personen, Organisationen, Rechte und
  Einsatzdaten.

---

## 3. Begriffe

| Begriff | Bedeutung |
|---|---|
| **Organisation** | Eine Einheit im Baum: Landkreis, Gemeinde-/Stadtfeuerwehr, Ortsfeuerwehr oder Kreiseinheit (z. B. Drohnengruppe). |
| **Konto** | Eine Person mit eigener Anmeldung. Konten werden nicht geteilt. |
| **Mitgliedschaft** | Verbindet ein Konto mit einer Organisation und einer **Organisationsrolle**. Eine Person kann mehreren Organisationen angehören. |
| **Organisationsrolle** | Was jemand in Open BOS darf (Rechte), z. B. Wehr-Admin oder Zuschauer. |
| **Einsatzrolle** | Welche Funktion jemand in einem bestimmten Einsatz hatte, z. B. Fernpilot. Dient der Dokumentation, nicht der Rechtevergabe. |
| **Einsatz** | Ein Ereignis mit Beginn, Ende, Stichwort und Ort, geführt von einer Wehr, mit weiteren beteiligten Wehren. |

---

## 4. Organisationsbaum

Ein frei aufbaubarer Baum, damit unterschiedliche Strukturen passen:

```text
Landkreis Stade
├── Stadtfeuerwehr Stade
│   ├── Ortsfeuerwehr Stade
│   ├── Ortsfeuerwehr Hagen
│   └── …
├── Samtgemeindefeuerwehr Harsefeld
│   ├── Ortsfeuerwehr Harsefeld
│   └── …
├── Gemeindefeuerwehr Jork
│   └── …
└── Kreisfeuerwehr (Kreiseinheiten, falls benötigt)
```

Die Ebene unter dem Landkreis ist die **Stadt-, Gemeinde- oder
Samtgemeindefeuerwehr**, darunter die **Ortsfeuerwehren**.

| Feld | Bedeutung |
|---|---|
| Name, Kurzname | z. B. „Ortsfeuerwehr Hagen“, „OF Hagen“ |
| Art | Landkreis · Stadt-/Gemeinde-/Samtgemeindefeuerwehr · Ortsfeuerwehr · Kreiseinheit |
| übergeordnete Organisation | bildet den Baum |
| Standort | für Wetter und Kartenmitte der Wehr |
| archiviert | aufgelöste Einheiten bleiben für alte Einsätze erhalten |

**Rechte vererben sich nach unten:** Wer auf Ebene der Stadtfeuerwehr eine
Rolle hat, hat sie auch in allen Ortsfeuerwehren darunter. Eine Rolle auf
Landkreisebene gilt im ganzen Landkreis.

---

## 5. Rollen und Rechte

### Organisationsrollen

| Rolle | gedacht für | darf |
|---|---|---|
| **Zuschauer** | Führungskräfte, Leitstelle, externe Stellen mit Konto | Livebilder, Karte, Wetter und Einsätze der Organisation ansehen |
| **Drohnenteam** | Fernpiloten, Luftraumbeobachter | zusätzlich: Einsätze anlegen und führen, Aufnahmen und Snapshots, Gastlinks, Quadranten zeichnen |
| **Wehr-Admin** | Verantwortliche der Wehr | zusätzlich: Konten und Mitgliedschaften der eigenen Organisation verwalten, Quellen der Wehr einrichten, Einsätze nachbearbeiten |

Dieselben Rollen gibt es **auf Landkreisebene**; sie gelten dann für alle
Wehren (z. B. „Kreis-Admin“ verwaltet alle Wehren, „Kreis-Zuschauer“ sieht alle
Einsätze lesend).

### Plattformrolle

| Rolle | darf |
|---|---|
| **Superadmin** | technische Verwaltung des Servers: Streaming-Ausgänge, E-Mail, Systemfunktionen, Organisationen anlegen. Unabhängig vom Organisationsbaum. |

### Rechte-Übersicht

| Aktion | Zuschauer | Drohnenteam | Wehr-Admin | Superadmin |
|---|:-:|:-:|:-:|:-:|
| Livebilder, Karte, Wetter | ✔ | ✔ | ✔ | ✔ |
| Einsätze der eigenen Wehr ansehen | ✔ | ✔ | ✔ | ✔ |
| Einsatz anlegen, Beteiligte und Rollen erfassen | – | ✔ | ✔ | ✔ |
| Weitere Wehr am Einsatz beteiligen | – | ✔ | ✔ | ✔ |
| Aufnahmen, Snapshots, Gastlinks | – | ✔ | ✔ | ✔ |
| Quellen (Drohnen) der Wehr einrichten | – | – | ✔ | ✔ |
| Konten und Rollen der Wehr verwalten | – | – | ✔ | ✔ |
| Organisationen anlegen | – | – | nur Kreis-Admin | ✔ |
| Streaming-Ausgänge, E-Mail, System | – | – | – | ✔ |

---

## 6. Was einer Wehr gehört

| Bereich | Zuordnung |
|---|---|
| **Quellen (Drohnen, Kameras)** | gehören **der einzelnen Wehr**, die die Drohne betreibt (in der Regel eine Ortsfeuerwehr); deren Mitglieder sehen sie, ebenso Rollen darüber (Gemeinde/Samtgemeinde, Landkreis). In Einsätzen sehen auch beteiligte Wehren die eingesetzten Quellen. |
| **Aufnahmen, Snapshots** | gehören zur Quelle und – falls vorhanden – zum Einsatz |
| **Gastlinks** | werden von einer Organisation erstellt und zeigen nur deren Quellen |
| **Ereignisprotokoll** | Einträge mit Organisation; Systemmeldungen sehen nur Superadmins |
| **Wetter-Standort** | je Organisation (Standort der Wache), sonst Kartenmitte |

---

## 7. Einsätze (Ausblick 0.22)

| Teil | Inhalt |
|---|---|
| **Einsatz** | Einsatznummer, Titel, Beginn, Ende, Status (laufend / beendet / nachbearbeitet), führende Wehr |
| **Alarmierung** | Alarmstichwort (z. B. „TH Person vermisst“), Einsatzadresse mit Koordinate, Alarmzeit, alarmierte Einheiten, Meldebild bzw. Alarmierungstext, Leitstellen-Einsatznummer (Freitext) |
| **Beteiligte Wehren** | weitere Organisationen mit Zeitpunkt der Hinzunahme |
| **Personen im Einsatz** | Konto oder freier Name (für Personen ohne Konto) mit Einsatzrolle und Zeitraum |
| **Eingesetzte Quellen** | welche Drohnen wann im Einsatz waren |
| **Medien** | Aufnahmen und Snapshots im Einsatzzeitraum, automatisch vorgeschlagen |
| **Verlauf** | Ereignisse des Einsatzes (Start, Signal, Aufnahmen, Notizen) |
| **Wetter** | Wetterstand zu Einsatzbeginn automatisch gespeichert |
| **Bericht** | PDF-Export aller Angaben |

**Einsatzrollen** (Vorschlag, Liste ist anpassbar):
Einsatzleiter · Abschnittsleiter Drohne · Fernpilot · Luftraumbeobachter ·
Kamera-/Payload-Operator · Dokumentation · Sonstige.

**Einsatznummer:** Datum plus laufende Nummer des Tages je führender Wehr,
z. B. „26.11.2026 – Einsatz 2“ (intern `2026-11-26-2`). Eine Nummer der
Leitstelle kann zusätzlich als Freitext erfasst werden.

**Sichtbarkeit:** Ein Einsatz ist sichtbar für Mitglieder der führenden Wehr,
der beteiligten Wehren und für Rollen auf übergeordneten Ebenen.

**Qualifikationen:** Je Konto werden Fernpilotennachweise erfasst
(EU-Kompetenznachweis A1/A3, Fernpilotenzeugnis A2, STS) mit Ablaufdatum.
Bei der Einsatzrolle „Fernpilot“ zeigt Open BOS einen Hinweis, wenn kein
gültiger Nachweis hinterlegt ist; der Einsatz wird dadurch nicht blockiert.

---

## 8. Übernahme beim Update

| heute | danach |
|---|---|
| Superadmin | Konto mit Plattformrolle Superadmin |
| Admin | Wehr-Admin der Start-Organisation |
| Zuschauer | Zuschauer der Start-Organisation |
| Quellen in `stream.yaml` | gehören der Start-Organisation |
| Gastlinks | gehören der Start-Organisation |

Die **Start-Organisation** (z. B. „Feuerwehr Stade“) und der **Landkreis**
darüber werden beim Update angelegt; der Name lässt sich anschließend ändern.
Weitere Wehren legt der Superadmin oder ein Kreis-Admin an. Die bisherige
Benutzerdatei bleibt als Sicherung erhalten.

---

## 9. Datenschutz

- Gespeichert werden nur Anmeldename, Anzeigename, optional E-Mail sowie
  Mitgliedschaften und Einsatzrollen.
- **Keine automatische Löschung** vorerst. Wehr-Admins können Einsätze
  bewusst löschen; das wird protokolliert. Eine einstellbare Löschfrist kann
  später ergänzt werden.
- Jede Änderung an Konten, Rollen und Einsätzen wird mit Person und Zeit
  protokolliert.
- Empfehlung: Abstimmung mit dem Datenschutzbeauftragten des Landkreises,
  bevor personenbezogene Einsatzdaten erfasst werden.

---

## 10. Ergebnisse der ersten Abstimmung

| Frage | Ergebnis |
|---|---|
| Struktur | Landkreis → Stadt-/Gemeinde-/Samtgemeindefeuerwehr → Ortsfeuerwehr |
| Drohnen | gehören einzelnen Wehren |
| Einsatzrollen | vorgeschlagene Liste passt vorerst; keine offizielle Vorgabe |
| Qualifikationen | ja, Fernpilotennachweise mit Ablaufdatum erfassen |
| Einsatznummern | Datum plus laufende Nummer des Tages |
| Löschfristen | vorerst keine automatische Löschung |
| Einsatzfelder | zusätzlich Alarmstichwort, Adresse und Alarmierungsdetails |

## 11. Noch offen

1. **Rollen auf Kreisebene:** Welche Personen oder Funktionen sollen
   wehrübergreifend sehen oder verwalten (siehe Erläuterung im Chat)?
2. **Personen ohne Konto:** Dürfen Einsatzkräfte ohne eigenes Konto mit
   Namen im Einsatz erfasst werden? (Vorschlag: ja.)
3. **Zählung der Einsatznummer:** je führender Wehr (Vorschlag) oder
   landkreisweit?

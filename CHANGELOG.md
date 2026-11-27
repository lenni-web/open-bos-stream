# Changelog

Alle wichtigen Änderungen an Open BOS Stream werden in dieser Datei dokumentiert.

Dieses Projekt orientiert sich an den Empfehlungen von
"Keep a Changelog" und verwendet Semantic Versioning für Releases.

---

## [Unreleased]

---

## [0.25.3] - 2026-11-27

Aufräum-Release (Rest aus dem Code-Review) und Vorbereitung der
DJI-Anbindung.

### Security

- MediaMTX-Prüfung: Unbekannte Aktionen werden abgelehnt statt pauschal
  erlaubt; die Prüfung auf lokale Aufrufe greift zuerst.
- Aufnahmen-Liste: Dateinamen werden immer maskiert und nur noch als
  Daten an die Knöpfe gebunden, nicht mehr in `onclick`-Code eingesetzt;
  Download- und Abspieladressen sind korrekt kodiert.
- Quellen ohne Wehr bleiben für alle sichtbar, bedienen (Aufnahmen,
  Gastlinks, Einsätze) dürfen sie aber nur Kreis-Admins und Superadmins.
- Alle Python-Abhängigkeiten gegen bekannte Sicherheitslücken geprüft
  (`pip-audit`): keine Funde.

### Changed

- Firewall (`--firewall configure`): Mit HTTPS wird zusätzlich TCP 8883
  für MQTT über TLS freigegeben – Vorbereitung für die DJI Cloud API, bei
  der sich die Fernsteuerungen per LTE-Stick oder Handy-Hotspot über das
  Internet verbinden. Solange kein MQTT-Broker läuft, bleibt der Port
  geschlossen.
- Das Browser-Testprotokoll wird nur noch für Kreis-Admins und
  Superadmins geladen (nur sie sehen die Systemseite).

### Removed

- Ungenutzter Endpunkt für den Einsatzort (die Einsatzkarte nutzt
  `/map/position`), zwei ungenutzte Hilfsfunktionen und die nicht mehr
  angezeigten Einzellisten für Aufnahmen und Snapshots.

---

## [0.25.2] - 2026-11-27

### Added

- Weitere Domains für denselben Server: `configure-server-access.sh
  --alias-domain NAME` (auch über `update.sh`/`install.sh`, mehrfach
  möglich) richtet in Caddy eine dauerhafte Weiterleitung auf die
  Hauptdomain ein, inklusive eigenem Zertifikat. Die Liste bleibt bei
  Updates erhalten und lässt sich mit `--remove-alias-domain` bzw.
  `--clear-alias-domains` ändern; im interaktiven Modus wird sie abgefragt.
  Die Systemseite zeigt die Weiterleitungs-Domains an.

---

## [0.25.1] - 2026-11-27

Sicherheits- und Aufräum-Update nach einem Code-Review.

### Security

- Wehr-Admins erhielten über die Konfiguration auch Sende-Schlüssel und
  Zugangsdaten fremder Drohnen, die sie nur sehen dürfen (z. B. im
  gemeinsamen Einsatz). Fremde Quellen kommen jetzt ohne Sende-Schlüssel,
  Passwörter und Zugangsdaten in Adressen; ältere RTMP-Eingänge werden
  Wehr-Admins nicht mehr ausgeliefert.
- Das Drohnenteam einer nur beteiligten Wehr konnte die Einsatzführung auf
  die eigene Wehr übertragen. Die Führung übergeben jetzt nur Admins der
  führenden Wehr (Feld für alle anderen gesperrt).
- Gastlink-Codes und Token-Parameter stehen nicht mehr im Klartext im
  Zugriffsprotokoll und im Stream-Protokoll.
- Quell-Adressen akzeptieren nur noch die Netzwerkprotokolle ihres Typs
  (z. B. kein `file:`, `concat:` oder `pipe:`); HTTP- und HLS-Quellen
  öffnet FFmpeg nur noch über Netzwerkprotokolle. Wehr-Admins können keine
  Quellen mehr einrichten, die der Server im eigenen bzw. internen Netz
  abruft (localhost, private Netze) – das bleibt Kreis-Admins vorbehalten.
- Passwörter werden mit 600.000 PBKDF2-Iterationen gespeichert (bisher
  240.000). Bestehende Passwörter werden beim nächsten Anmelden
  automatisch umgestellt; andere Sitzungen dieses Kontos enden dabei
  einmalig.
- Anmeldungen mit unbekanntem Benutzernamen dauern gleich lange wie mit
  falschem Passwort (Benutzernamen nicht mehr über die Antwortzeit
  erkennbar).
- Fehlermeldungen an den Browser enthalten keine Serverpfade bzw.
  FFmpeg-Ausgaben mehr (Offline-Karte, Aufbereitung von Aufnahmen).

### Changed

- Rechte eines Kontos werden kurz zwischengespeichert statt bei jeder
  Anfrage neu aus der Datenbank berechnet; jede Änderung an Organisationen,
  Mitgliedschaften oder Einsätzen wirkt trotzdem sofort.
- Abhaken von Checklisten benötigt weniger Datenbankabfragen; eine
  gemeinsame Instanz des Checklisten-Dienstes.
- Ungenutzte Stilregeln aus älteren Oberflächenständen entfernt (rund 600
  Zeilen CSS); doppelte Beschriftungen in den Wasserentnahme-Popups
  bereinigt.
- Versehentlich eingecheckte Build-Dateien (`build/`) aus dem Repository
  entfernt und künftig ignoriert.

### Fixed

- Smartphone: Ereignisprotokoll und Streaming-Ausgänge auf der Übersicht
  ragten bei vielen bzw. langen Einträgen über den rechten Rand hinaus. Die
  Spalten bleiben jetzt in der Bildschirmbreite, lange Dateinamen und
  Adressen werden umgebrochen.

---

## [0.25.0] - 2026-11-27

### Added

- **Checklisten** als eigenes Modul mit eigenem Menüpunkt (Reiter
  Checklisten, Vorlagen, Dokumente):
  - **Vorlagen** legen Drohnenteams und Admins auf Landkreisebene an:
    Positionen mit Abschnitt, Hinweis und Kennzeichnung als Pflicht;
    Vorlagen lassen sich bearbeiten (neue Version) und archivieren.
  - **Eigene Listen**: Jede Wehr kann eigene Checklisten anlegen – aus einer
    Vorlage oder komplett frei mit eigenen Positionen –, aber keine
    Vorlagen.
  - **Im Einsatz**: Knopf „Checkliste hinzufügen“ auf der Einsatzseite
    übernimmt eine Vorlage; alle Beteiligten haken ab und tragen
    Anmerkungen ein (mit Name und Uhrzeit). Nach dem Abschluss des
    Einsatzes ist die Liste gesperrt; ändern dürfen dann nur Admins der
    führenden Wehr. Eigene Listen ohne Einsatz werden über „Abschließen“
    gesperrt.
  - **Pflichtpositionen**: Beim Beenden bzw. Abschließen eines Einsatzes
    (und einer eigenen Liste) erscheint ein Hinweis auf offene
    Pflichtpositionen.
  - Checklisten stehen mit allen Häkchen und Anmerkungen im
    Einsatzbericht.
  - **Dokumente**: Der Landkreis stellt einheitliche Unterlagen bereit
    (PDF, Office, OpenDocument, Text, Bilder; bis 25 MB), alle Wehren
    können sie öffnen und herunterladen.
- Widmung in der Seitenleiste und auf der Anmeldeseite: „Gemacht für die
  Freiwilligen Feuerwehren – mit Dank an alle Ehrenamtlichen, besonders
  der FF Agathenburg.“

---

## [0.24.4] - 2026-11-27

### Added

- **Mein Konto** im Benutzermenü: Anzeigename und E-Mail ändern, eigene
  Rollen und Fernpilotennachweise ansehen, Passwort ändern. Nach einer
  Passwortänderung bleibt das aktuelle Gerät angemeldet, alle anderen
  Sitzungen enden. Falsche Eingaben des bisherigen Passworts werden wie
  bei der Anmeldung gebremst.
- **Aufnahmen je Wehr**: Die Seite „Aufnahmen“ steht jetzt allen
  Drohnenteams offen und zeigt die Videos und Snapshots der Drohnen der
  eigenen Wehr(en) mit Angabe der Drohne. Drohnenteams können ansehen,
  herunterladen und „Behalten“ setzen; löschen dürfen Admins der Wehr.
  Dateien ohne erkennbare Quelle sehen weiterhin nur Kreis-Admins und
  Superadmins. Aufnahme- und Snapshot-Steuerung bleiben Superadmins
  vorbehalten.

### Changed

- Funktionsübersicht (PDF) um Einsätze, Einsatzkarte, Übungen,
  Push-Benachrichtigungen und Lastüberwachung ergänzt.
- In der Kopfzeile steht der Anzeigename statt des Benutzernamens.

---

## [0.24.3] - 2026-11-27

### Changed

- Keine feste Obergrenze mehr für gleichzeitig aktive Quellen (bisher 8);
  ebenso für Gastlinks und Einsätze. Ab neun Quellen weist die
  Quellenverwaltung auf die Serverlast hin.
- Keine feste Obergrenze mehr für gleichzeitige Aufnahmen (bisher 4):
  Automatische und manuelle Aufnahmen lassen sich für beliebig viele Quellen
  parallel nutzen; Speicherschutz und Lastüberwachung bleiben aktiv.

### Added

- Überwachung der Serverauslastung (CPU, Arbeitsspeicher, Systemlast je
  Kern) als Mittelwert der letzten 30 Sekunden mit Hysterese, damit kurze
  Spitzen keinen Hinweis auslösen.
  - Bei hoher bzw. sehr hoher Last erscheint auf allen Seiten ein Hinweis
    mit Ursache und Empfehlung (Quellen deaktivieren, sparsames
    Vorschauprofil).
  - Wechsel der Laststufe stehen im Ereignisprotokoll.
  - Hält eine Überlastung länger als 2 Minuten an, gibt es eine
    Benachrichtigung per E-Mail und Push (für Kreis-Admins und Superadmins,
    abschaltbar), samt Entwarnung.

---

## [0.24.2] - 2026-11-27

### Changed

- Einsatzkarte: Eine gezeichnete Fläche lässt sich direkt auf der Karte
  abschließen – ersten Punkt erneut antippen, doppelklicken oder Enter.
  Danach setzen Klicks keine weiteren Punkte mehr; das Namensfeld wird
  geöffnet (ist schon ein Name eingetragen, wird sofort gespeichert).
  „Weiterzeichnen“ öffnet die Fläche wieder, Escape bricht das Zeichnen ab.

---

## [0.24.1] - 2026-11-27

### Changed

- Farben des Logos als Akzente in der Oberfläche: Seitenleiste in
  Logo-Dunkelblau mit rotem Strich am aktiven Menüpunkt, Überschriften in
  Dunkelblau, rote Linie unter der Kopfzeile, aktiver Punkt der
  Smartphone-Leiste in Dunkelblau, Anmeldeseite mit dunkelblauem
  Hintergrund. Hell- und Dunkelmodus sind angepasst.
- Beschreibung auf der Anmeldeseite an die Ausrichtung auf Drohneneinsätze
  angepasst.

---

## [0.24.0] - 2026-11-27

### Added

- **Einsatzkarte mit Quadranten**: Auf der Karte einen Einsatz wählen,
  dann Raster aufziehen (z. B. 3 × 3, benannt A1 … C3, optional mit Präfix),
  Suchflächen frei zeichnen und den Einsatzort setzen. Jeder Quadrant hat
  Status (offen, zugewiesen, wird abgesucht, abgesucht, Fund / Hinweis),
  Zuständigkeit (Drohne / Trupp) und Notiz.
  - Alle, die den Einsatz sehen dürfen, sehen neue und geänderte Quadranten
    nach spätestens zwei Sekunden – auch über Einsatz-Gastlinks (dort nur
    lesend).
  - Zeichnen und Ändern dürfen die Drohnenteams der beteiligten Wehren;
    Statuswechsel stehen im Einsatzverlauf.
  - Übersicht der Quadranten auf der Einsatzseite und im Einsatzbericht.
- **Übungen**: Ein Einsatz lässt sich beim Anlegen oder nachträglich als
  Übung kennzeichnen. Übungen sind überall blau markiert (Einsatzliste,
  Einsatzseite, Karte, Gastansicht), heißen im Bericht „Übungsbericht“
  mit Vermerk „ÜBUNG – kein Realeinsatz“, und die Push-Nachricht beginnt
  mit „Übung:“. Das Umstellen steht im Verlauf.

---

## [0.23.0] - 2026-11-27

### Added

- **Einsätze** als eigener Menüpunkt (auf dem Smartphone in der unteren
  Leiste, mit Zähler laufender Einsätze):
  - Anlegen mit führender Wehr, Alarmzeit, Alarmstichwort, Einsatzadresse,
    Alarmierungstext, alarmierten Einheiten und Leitstellen-Nummer.
  - Einsatzkennung aus Datum und Alarmzeit (z. B. `2026-11-26-1432`, bei
    gleicher Minute mit Zusatz `-2`); eine korrigierte Alarmzeit ändert die
    Kennung mit.
  - Weitere Wehren beteiligen: Sie sehen den Einsatz und – solange er
    läuft – die Livebilder der eingesetzten Drohnen, auch wenn diese einer
    anderen Wehr gehören.
  - Personen mit Einsatzrolle (Einsatzleiter, Abschnittsleiter Drohne,
    Fernpilot, Luftraumbeobachter, Payload-Operator, Dokumentation,
    Sonstige), auch ohne eigenes Konto; Hinweis bei Fernpiloten ohne
    gültigen Nachweis.
  - Drohnen dem Einsatz zuordnen und wieder herausnehmen (mit Zeitraum).
  - Wetter am Einsatzort wird beim Anlegen festgehalten und lässt sich neu
    erfassen.
  - Aufnahmen und Snapshots der Einsatzdrohnen im Einsatzzeitraum werden
    automatisch zugeordnet und sind für alle Beteiligten abrufbar.
  - Verlauf mit allen Änderungen und eigenen Notizen; Lage- und
    Abschlussbericht.
  - Einsatzbericht als druckfertige Seite („Drucken / Als PDF speichern“).
  - Status laufend → beendet → abgeschlossen; abgeschlossene Einsätze
    ändern und löschen nur Admins der führenden Wehr. Keine automatische
    Löschung.
- **Einsatz-Gastlinks** für externe Stellen: zeigen alle Drohnen des
  Einsatzes (neu zugeordnete erscheinen automatisch) und werden mit dem
  Einsatzende gesperrt. Öffnen und Sperren stehen im Einsatzverlauf.
- Push-Benachrichtigung „Neuer Einsatz“ für alle, die den Einsatz sehen
  dürfen; ein Tippen öffnet den Einsatz.

### Changed

- „Wetter“ steht auf dem Smartphone jetzt unter „Mehr“, damit „Einsätze“
  in die untere Leiste passt.
- Organisationen, die in Einsätzen vorkommen, lassen sich nicht mehr
  löschen, nur archivieren.

---

## [0.22.0] - 2026-11-27

### Added

- Push-Benachrichtigungen (Web Push) für Smartphone, Tablet und Computer:
  Im Benutzermenü unter „Benachrichtigungen“ schaltet jedes Konto sie pro
  Gerät ein, wählt die Ereignisse und kann eine Testnachricht senden.
  Gemeldet werden dieselben Störungen wie per E-Mail. Meldungen zu einer
  Quelle erhalten nur Konten, die diese Drohne sehen dürfen; serverweite
  Störungen (Streaming-Server, Speicher, Neustart) nur Kreis-Admins und
  Superadmins. Eine Entwarnung ersetzt die Störungsmeldung auf dem Gerät.
- Auf iPhone und iPad funktionieren Benachrichtigungen nur in der
  installierten App (ab iOS 16.4); der Dialog verweist dann auf die
  Installationsanleitung. Voraussetzung ist eine HTTPS-Adresse.
- Neue Abhängigkeit `cryptography` (Verschlüsselung nach RFC 8291/8292).
  Der Serverschlüssel liegt in `config/webpush.key` (0600) und gehört in
  die Sicherung, sonst müssen alle Geräte neu angemeldet werden.

### Changed

- Der Menüpunkt „Medien“ heißt jetzt „Aufnahmen“; der Filter unterscheidet
  Videos und Snapshots.
- Der interne Entwurf des Datenmodells ist nicht mehr Teil des Repositorys.

### Fixed

- Smartphone: Die Seite ließ sich seitlich verschieben, wenn einzelne
  Inhalte (z. B. lange Drohnennamen) breiter als der Bildschirm wurden.
  Die Seite ist jetzt auf die Bildschirmbreite begrenzt; lange Namen werden
  gekürzt.

---

## [0.21.1] - 2026-11-27

### Fixed

- Abmelden im Benutzermenü funktionierte seit 0.21.0 nicht mehr.

### Changed

- Organisation und Konten haben einen eigenen Menüpunkt **„Organisation“**
  (für Wehr-Admins, Kreis-Admins und Superadmins) statt eines Bereichs am
  Ende der Einstellungen.
- Neuer Test: Jede in den Seiten per Klick aufgerufene Funktion muss im
  JavaScript vorhanden sein.

---

## [0.21.0] - 2026-11-27

### Added

- **Organisationen:** Landkreis, Stadt-/Gemeinde-/Samtgemeindefeuerwehren,
  Ortsfeuerwehren und Kreiseinheiten als Baum. Verwaltung unter
  „Einstellungen → Organisation und Konten“.
- **Rollen je Organisation:** Zuschauer, Drohnenteam und Wehr-Admin; Rechte
  vererben sich nach unten. Wehr-Admin auf Landkreisebene ist Kreis-Admin.
  Die technische Plattformrolle Superadmin bleibt.
- **Quellen gehören einer Wehr.** Konten sehen nur Quellen ihrer
  Organisationen – in der Übersicht, im Vollbild, bei Livebild-Abrufen über
  Caddy und MediaMTX, im Ereignisprotokoll und bei Gastlinks.
- **Fernpilotennachweise** (A1/A3, A2, STS) mit Nummer und Ablaufdatum je
  Konto; abgelaufene Nachweise werden markiert.
- Konten mit Anzeigename, optionaler E-Mail, Sperre und Änderungsprotokoll;
  eigene Daten und Passwort über `/api/org/me`.
- Drohnenteams erstellen Gastlinks für Quellen ihrer Organisation.
- Neuer Menüpunkt **Livebilder** mit allen Videos, Gastlink, Snapshot und
  Aufnahme. Die **Übersicht** zeigt stattdessen die Gesamtlage: alle Quellen
  kompakt mit Status, Wehr, Auflösung und Aufnahme, dazu Flugwetter,
  Ereignisprotokoll und Weiterleitungen.
- Datenbank SQLite (`config/open-bos.db`) mit automatischer Migration über
  Alembic; neue Abhängigkeiten SQLAlchemy 2.1.9 und Alembic 1.20.1.

### Changed

- Beim ersten Start werden Landkreis und Start-Organisation angelegt, die
  Konten aus `config/users.yaml` übernommen (Superadmin → Superadmin und
  Kreis-Admin, Admin → Wehr-Admin, Viewer → Zuschauer) und bestehende
  Quellen und Gastlinks der Start-Organisation zugeordnet. Die alte Datei
  bleibt als `users.yaml.importiert` erhalten.
- Serverweite Einstellungen (Wetter, Systemseite, Systemstatus, Diagnose,
  Konfigurationstest) nur noch für Kreis-Admins und Superadmins. Wehr-Admins
  bearbeiten nur Quellen ihrer Organisationen.
- Benutzermenü zeigt Anzeigename und Rollen (z. B. „Wehr-Admin · OF Hagen“).
- Videos laufen nur noch auf der Seite „Livebilder“; beim Wechsel zu
  Übersicht, Karte oder Wetter werden sie beendet; das spart Mobilfunkdaten.
- Smartphone-Leiste: Übersicht, Livebilder, Karte, Wetter und „Mehr“.

### Fixed

- Der Dialog „Als App installieren“ fehlte für Zuschauer; der Menüeintrag
  öffnete bei ihnen nichts.

### Security

- Livebild-Abrufe (Caddy `forward_auth` und MediaMTX-Medientoken) prüfen die
  Zugehörigkeit der Quelle zur Organisation des Kontos.

---

## [0.20.5] - 2026-11-26

### Changed

- Neuer Name in der Oberfläche: **Open BOS Drohnen** (vorher „Open BOS
  Stream“) – in Seitenleiste, Anmeldung, Seitentiteln, Gastansicht,
  installierter App (Kurzname „BOS Drohnen“), E-Mails, Ereignisprotokoll und
  Funktionsübersicht. Technische Namen (Repository, Dienste, Pfade wie
  `/opt/open-bos-stream`) bleiben unverändert.

---

## [0.20.4] - 2026-11-26

### Changed

- Wetterseite: Die Vorhersage der nächsten 24 Stunden ist aufklappbar und
  anfangs zugeklappt.

---

## [0.20.3] - 2026-11-26

### Added

- Wetter: Der Kp-Index heißt jetzt „Satellitennavigation“ und zeigt den
  Zustand im Klartext (ruhig, unruhig, Sturm, starker Sturm) mit dem
  Kp-Wert darunter.
- Kurzinfos zu jeder Wetterangabe: beim Darüberfahren als Hinweis, beim
  Antippen direkt in der Kachel (Übersicht und Wetterseite).
- Wetterseite: aufklappbarer Abschnitt „Was bedeuten die Werte?“ mit
  Erklärungen zu Wind in 120 m, Taupunkt, Wolkenbasis, Kp-Index,
  bürgerlicher Dämmerung und weiteren Angaben.

### Changed

- Wetterseite: Zusammenfassung „Wetter für den Flugbetrieb“ oben, darunter
  das Niederschlagsradar und danach die Vorhersage der nächsten 24 Stunden
  als eigene Karte.

---

## [0.20.2] - 2026-11-26

### Changed

- Kartenmenü: Die Wasserentnahmestellen sind nach der feuerwehrüblichen
  Einteilung zu zwei Schaltern zusammengefasst – **Hydranten** (abhängige
  Löschwasserversorgung) und **Unabhängige Löschwasserstellen**
  (Saugstellen, Behälter/Teiche, Brunnen, weitere). Eine Farblegende
  unterscheidet die Arten weiterhin.
- Lagertanks ohne Inhaltsangabe erscheinen nur noch als Ring, damit sie
  sich von verlässlichen Wasserstellen abheben.

---

## [0.20.1] - 2026-11-26

### Added

- Wetter: Taupunkt mit Taupunktdifferenz und geschätzter Wolkenuntergrenze
  sowie Sonnenauf- und -untergang mit bürgerlicher Dämmerung (auf dem
  Server berechnet, ohne weiteren Dienst).
- Wetter-Ampel: Hinweise bei Nebel- und Beschlaggefahr (Taupunktdifferenz
  bis 2 °C), tiefer Wolkenuntergrenze (unter 200 m), Vereisungsgefahr und
  Dunkelheit nach Ende der bürgerlichen Dämmerung (Nachtflugregeln).

### Changed

- Wetterseite auf allen Bildschirmgrößen einspaltig: Niederschlagsradar
  oben, Wetterangaben und Vorhersage darunter.

---

## [0.20.0] - 2026-11-26

### Added

- Online-Grundkarte **basemap.de** (amtliche Vektorkarte für Deutschland,
  BKG und Vermessungsverwaltungen), in der dunklen Darstellung mit
  Nachtstil.
- **Luftbild Niedersachsen** (LGLN DOP20, 20 cm, CC BY 4.0) mit
  Beschriftungen von basemap.de; außerhalb Niedersachsens die Karte.
- Auswahl der Grundkarte im Menü „Kartenebenen“ (Karte, Luftbild,
  Offline-Karte); jeder Browser merkt sich die Wahl. Wasserentnahmestellen,
  Geozonen und Regenradar bleiben beim Wechsel erhalten.
- Ist der Online-Dienst nicht erreichbar, zeigt die Karte die Offline-Karte
  mit Hinweis. Ohne installierte MBTiles-Datei funktioniert die Karte jetzt
  trotzdem.
- Alle Kartenabrufe laufen über den Server mit Zwischenspeicher:
  Vektorkacheln komprimiert, Luftbilder als WebP (rund 90 % kleiner).
- Neue Einstellungen `map.online` und `map.base_map` in `stream.yaml`.

### Changed

- **MapLibre GL JS 6.19.0** (vorher 5.24.1), eingebunden als Modul; behebt
  u. a. Ladeprobleme auf iPhone und iPad nach App-Wechseln und die
  Sicherheitslücke GHSA-jrc7-96c5-q579.
- Die Radarseite nutzt basemap.de als Grundkarte, damit Regengebiete auch
  außerhalb des Landkreises eingeordnet werden können.
- Die Quellenangaben der Karte sind eingeklappt (Symbol ⓘ), damit sie die
  Karte nicht verdecken.
- Kartenadressen werden relativ ausgeliefert und im Browser vervollständigt;
  das passt auch hinter einem HTTPS-Proxy.
- Wasser-Ebenen liefern die rohen OSM-Tags nicht mehr mit aus.

### Fixed

- Wetterseite: Der Schieberegler der Radar-Zeitleiste hat eine feste Breite
  und springt beim Abspielen nicht mehr; die Zeitangabe steht darunter.

---

## [0.19.1] - 2026-11-26

### Added

- Neuer Menüpunkt **Wetter** (für alle Rollen): alle Wetterangaben der
  Übersicht mit Vorhersage über 24 Stunden und eine eigene Radarkarte.
- Radar-Zeitleiste: Schieberegler von zwei Stunden zurück bis 90 Minuten
  voraus im 10-Minuten-Takt, „Abspielen“ als Animation der
  Niederschlagsbewegung, Farblegende in mm/h, Markierung des
  Wetter-Standorts.
- Die Wetterkarte der Übersicht führt mit „Wetter und Radar öffnen“ zur
  neuen Seite.
- Smartphone-Menü: In der unteren Leiste stehen Übersicht, Karte und Wetter,
  alle weiteren Bereiche (Medien, Einstellungen, System und künftige Module)
  öffnen sich über „Mehr“. Das Menü wird aus einer gemeinsamen Liste erzeugt.

### Changed

- Untertitel der Anwendung: „BOS Drohnen Suite“ statt „BOS Streaming Suite“.
- Reihenfolge im Menü: Übersicht, Karte, Wetter, Medien, Einstellungen,
  System.
- Die Ampel betrachtet für ihren Ausblick weiterhin nur die nächsten sechs
  Stunden, auch wenn die Vorhersage nun 24 Stunden umfasst.
- Radarabrufe beim DWD laufen mit bis zu acht parallelen Anfragen;
  vergangene Radarbilder bleiben eine Stunde zwischengespeichert.

---

## [0.19.0] - 2026-11-26

### Added

- Wetter für den Flugbetrieb: Die Übersicht zeigt Messwerte der nächsten
  DWD-Station, Wind in 120 m Höhe, Böen, Temperatur, Niederschlag, Sicht,
  den Kp-Index, amtliche DWD-Warnungen und eine Vorhersage der nächsten
  Stunden.
- Wetter-Ampel mit einstellbaren Grenzwerten (Wind, Böen, Temperatur,
  Niederschlag, Sicht); berücksichtigt auch Kp-Index, DWD-Warnungen ab
  „markant“ und die erste kritische Stunde der Vorhersage.
- Karte: Niederschlagsradar des DWD als Ebene mit Vorhersage bis +90 Minuten
  und einstellbarer Deckkraft sowie eine Wetteranzeige für die Kartenmitte;
  auch in der Gastansicht.
- Einstellungen → Wetter: Standort (sonst Kartenmitte), Grenzwerte und
  Abschalten ohne Internetzugang. Wird separat gespeichert und im
  Ereignisprotokoll vermerkt.
- Alle Wetterabrufe laufen über den Server mit Zwischenspeicher; fällt eine
  Quelle aus, bleiben die übrigen sichtbar.
- Als App installieren: Eintrag im Benutzermenü mit Kurzanleitung für
  iPhone/iPad, Android und Computer; auf Android mit direkter Schaltfläche
  „Jetzt installieren“, sofern der Browser sie anbietet.
- Auf Smartphones und Tablets erscheint oben auf der Übersicht einmalig ein
  Hinweis zur Installation („Später“ für sieben Tage, „Nicht mehr
  anzeigen“). In der installierten App und in der Gastansicht nicht.
- Funktionsübersicht (PDF) um Flugwetter, App-Installation und
  RTSP-Weiterleitung über den Pi ergänzt.

---

## [0.18.12] - 2026-11-26

### Added

- RTSP vom Controller weiterleiten: RTSP-Quellen bieten Vorlagen für
  DJI Pilot 2, Parrot SkyController, Skydio Enterprise Controller und Autel
  Smart Controller. Die Vorlage setzt Transport und das Profil
  „Copy-Reparatur · geringe Latenz“; zusammen mit einem SRT-Ausgang leitet
  ein Raspberry Pi vor Ort das Bild ohne Neukodieren an den Server weiter.
- `scripts/pi-controller-network.sh`: richtet am Pi die Netzwerkverbindung
  zum Controller ein (Controller vergibt die Adresse oder Pi vergibt sie),
  ohne dem Mobilfunk die Standardroute zu nehmen; mit Statusanzeige.
- Noch nicht mit echten Controllern getestet.

---

## [0.18.11] - 2026-11-26

### Fixed

- Karte: Die Ebene „Sonstige Wasserstellen“ zeigte alle Lagertanks aus
  OpenStreetMap als Wasserentnahmestelle an, darunter Güllebehälter,
  Gas-, Abwasser-, Silage- und Kraftstofftanks. Tanks mit einem anderen
  Inhalt als Wasser werden jetzt ausgefiltert. Tanks ohne Inhaltsangabe
  bleiben sichtbar und heißen „Lagertank (Inhalt unbekannt)“,
  Trinkwasserstellen „Trinkwasserstelle“.
- Als Umriss erfasste Wasserstellen erscheinen als ein Punkt in ihrer
  Mitte statt als Ring aus Punkten an jedem Eckpunkt.

### Changed

- Alle Wasserentnahmestellen außer Hydranten erscheinen einheitlich ab
  Zoomstufe 13; Hydranten wegen ihrer Menge weiterhin ab 14.
- Kartenebenen ohne Daten (derzeit „Offene Wasserentnahmestellen“)
  werden in der Ebenenliste ausgeblendet.
- Python-Abhängigkeiten aktualisiert: Pillow 12.3.0 → 13.0.0 (behebt 43
  bekannte Sicherheitslücken; Open BOS Stream erzeugt mit Pillow nur
  eigene Bilder und war praktisch nicht angreifbar), FastAPI 0.138.0 →
  0.165.0, Starlette 1.3.1 → 1.10.0, Uvicorn 0.49.0 → 0.54.0. FastAPI
  bringt neu `opentelemetry-api` mit.
- Entwicklung: httpx2 2.16.2, GitHub Actions auf v7 (checkout,
  setup-python, setup-node).

### Security

- Karte: Quellenangaben aus MBTiles-Dateien werden nur noch als Text an
  MapLibre übergeben. Der HTML-Filter von MapLibre 5 lässt sich umgehen
  (GHSA-jrc7-96c5-q579, behoben erst in MapLibre 6).
- Popups der Wasser-Ebenen setzen Werte aus OpenStreetMap maskiert ein.

---

## [0.18.10] - 2026-11-26

### Added

- SRT-Empfang: Quellen vom Typ „Sender → Server“ können wahlweise per RTMP
  (Drohnen-Apps) oder per SRT empfangen. SRT läuft über UDP 8890, gleicht
  Paketverluste aus und eignet sich mit typisch 0,5–1 s Verzögerung für
  Sender über Mobilfunk, z. B. einen Raspberry Pi mit HDMI-Capture-Card.
  Anmeldung mit `streamid=publish:<id>:token=<TOKEN>`; Pfad, Token und
  Protokoll werden geprüft.
- Die Einstellungen zeigen je nach Protokoll die passende Empfangsadresse
  mit Hinweisen zur Latenz.
- Raspberry Pi vor Ort: neues Quellenprofil „Transcodieren · geringe Latenz
  (Mobilfunk)“ für die Capture-Card – ein Schlüsselbild pro Sekunde, keine
  B-Frames, minimale Puffer; mit dem Hardware-Encoder `h264_v4l2m2m` des
  Pi 4 oder `libx264` mit `ultrafast`/`zerolatency`.
- SRT-Streaming-Ausgänge senden latenzarm: kein Zwischenpuffern und – sofern
  die Adresse nichts anderes vorgibt – ein SRT-Puffer von 400 ms.

### Changed

- Firewall (`--firewall configure`): UDP 8890 für SRT-Sender wird
  freigegeben. MediaMTX lauscht dafür ausdrücklich auf `:8890`.
- Quellentypen klarer benannt: „Sender → Server (RTMP oder SRT)“ und
  „SRT abrufen (Server holt Stream)“.

---

## [0.18.9] - 2026-11-24

### Changed

- Das Ereignisprotokoll wird jetzt vom Server geführt statt vom Browser.
  Einträge entstehen auch ohne geöffnete Oberfläche, sind für alle Admins
  und Superadmins gleich, überstehen Neustarts und Updates und bleiben
  30 Tage erhalten (`config/event_log.jsonl`). Bisher war das Protokoll
  nach dem Schließen des Tabs leer.
- Erfasst werden Signalwechsel der Quellen, Aufnahmen, Snapshots,
  Löschungen, Weiterleitungen, Streaming-Server, Speicher,
  Konfigurationsänderungen, Gastlinks, E-Mail-Benachrichtigungen sowie
  Start und Ende des Dienstes. Bedienaktionen nennen den auslösenden
  Benutzer.
- „Leeren“ blendet Einträge nur im eigenen Browser aus.

---

## [0.18.8] - 2026-11-24

### Added

- Automatische Aufnahme pro Quelle: In den Einstellungen unter
  „Automatisch aufnehmen“ lassen sich bis zu vier Quellen anhaken, die
  beim Eingangssignal selbstständig aufnehmen. Mehrere Aufnahmen laufen
  parallel, auch neben der manuellen Aufnahme der Medienquelle (insgesamt
  höchstens vier gleichzeitig).
- Videokacheln zeigen eine laufende Aufnahme mit Dauer an.

### Changed

- Speicherschutz, Herunterfahren und E-Mail-Benachrichtigungen
  berücksichtigen alle laufenden Aufnahmen; Meldungen nennen die Quelle.
- Die bisherige Einstellung „Aufnahme automatisch steuern“ wird beim
  Update übernommen: Die gewählte Medienquelle nimmt weiter automatisch auf.

### Fixed

- „Konfiguration testen“ und „Änderungen speichern“ behalten nach dem
  Prüfen ihre kurzen Beschriftungen auf dem Smartphone.
- Änderungen an Benachrichtigungen und automatischer Aufnahme markieren
  die allgemeine Konfiguration nicht mehr als „ungespeichert“; sie werden
  separat gespeichert.

---

## [0.18.7] - 2026-11-24

### Changed

- Funktionsübersicht (PDF auf der Anmeldeseite) aktualisiert: Gastlinks
  unter „Zugriff & Sicherheit“, E-Mail-Benachrichtigung bei Störungen unter
  „Betrieb & Diagnose“ und Hell-/Dunkelmodus unter „Überall nutzbar“.
- README überarbeitet: vollständige Funktionsliste, neuer Abschnitt
  „Oberfläche“ (Seitenleiste, Status, Benutzermenü, Dunkelmodus),
  aktualisierte Beschreibung der Zuschauerrolle und eigene Kapitel
  „Aufnahmen und Snapshots“ sowie „Betrieb“ (Benachrichtigungen, Zeitzone).
- Roadmap: E-Mail-Benachrichtigungen, Gastlinks und neue Oberfläche als
  erledigt markiert; Einsatzprotokoll-Export und weitere
  Benachrichtigungskanäle als nächste Schritte aufgenommen.

---

## [0.18.6] - 2026-11-24

### Fixed

- Uhrzeiten vom Server stimmen jetzt mit der deutschen Zeit überein. Läuft
  der Server in UTC, lagen Zeitangaben in E-Mails, Gastlink-Meldungen, den
  Dateinamen von Aufnahmen und Snapshots sowie im Journal im Winter eine und
  im Sommer zwei Stunden zurück. Die Anwendung verwendet nun Europe/Berlin
  mit automatischer Sommer-/Winterzeit (änderbar über die
  Umgebungsvariable `OPEN_BOS_TIMEZONE`). Die Systemzeit des Servers bleibt
  unverändert.

---

## [0.18.5] - 2026-11-24

### Changed

- Smartphone: Die Speichern-Leiste der Einstellungen ist deutlich kompakter
  (Statuszeile und drei Knöpfe „Testen“, „Wiederherstellen“, „Speichern“
  in einer Reihe) und schwebt nur noch bei ungespeicherten Änderungen über
  dem Inhalt. Sonst steht sie am Seitenende.

---

## [0.18.4] - 2026-11-24

### Added

- Gastlinks im Ereignisprotokoll: Erstellen, Öffnen durch einen Gast,
  Sperren und Ablauf erscheinen bei allen Admins und Superadmins mit
  Uhrzeit, auch wenn ein anderer Admin den Link erstellt hat. Nach dem
  Neuladen der Seite werden die Ereignisse der letzten 24 Stunden erneut
  angezeigt. Zuschauer und Gäste erhalten diese Meldungen nicht.

---

## [0.18.3] - 2026-11-24

### Added

- Gastlinks: Admins und Superadmins teilen ausgewählte Livebilder zeitlich
  begrenzt (höchstens 48 Stunden) mit externen Stellen ohne eigenes Konto.
  Erstellen in der Übersicht mit Link, QR-Code und Teilen-Funktion;
  Verwaltung und Sperren unter Einstellungen → „Gastlinks“.
- Reduzierte Gastansicht mit den freigegebenen Livebildern und der Karte,
  Anzeige der Restgültigkeit und Hell/Dunkel-Umschalter.

### Security

- Gäste erhalten nur die Streams der freigegebenen Quellen: Caddy und die
  MediaMTX-Leserprüfung kontrollieren den angefragten Pfad. Abgelaufene oder
  gesperrte Gastlinks beenden die Gastansicht sofort.
- Gastlinks werden nur als SHA-256-Hash gespeichert (`config/guest_links.json`,
  Rechte 0600). „Gast“ ist keine zuweisbare Benutzerrolle.

---

## [0.18.2] - 2026-11-24

### Added

- E-Mail-Benachrichtigungen bei Störungen: Quelle ohne Signal, Streaming-
  Server nicht erreichbar, Speicher knapp, Aufnahme abgebrochen,
  Streaming-Ausgang unerwartet beendet und Serverstart. Mit Wartezeit gegen
  kurze Aussetzer, höchstens einer Meldung je Störung alle zehn Minuten und
  Entwarnung, sobald wieder alles läuft. Einrichtung und Testnachricht in den
  Einstellungen (nur Superadmin).

### Security

- Das SMTP-Passwort liegt getrennt in `config/notifications.secret`
  (Rechte 0600) und wird nie an den Browser ausgeliefert. Admins sehen
  weder Mailserver noch Empfängeradressen; Stream-Schlüssel in
  FFmpeg-Fehlermeldungen werden vor dem Versand entfernt.

---

## [0.18.1] - 2026-11-24

### Security

- Namen und Ziel-URLs von Streaming-Ausgängen werden in der Übersicht und in
  den Einstellungen maskiert eingesetzt. Ein präparierter Ausgangsname konnte
  bisher HTML oder Skriptcode in die Seite einschleusen (Review N1). Start
  und Stopp laufen nicht mehr über im HTML zusammengesetzten Code.
- MediaMTX 1.21.4 schreibt Passwörter und Tokens aus Anmeldeanfragen nicht
  mehr ins Debug-Protokoll.

### Changed

- MediaMTX-Standardversion von 1.21.1 auf 1.21.4 angehoben (Fehlerbehebungen
  u. a. bei UDP/WebRTC, HTTP/2 und Weiterleitungen). Bestehende Installationen
  aktualisieren MediaMTX mit `./scripts/update.sh --install-mediamtx`.
- Python-Abhängigkeiten auf aktuelle Fehlerbehebungsversionen aktualisiert,
  u. a. certifi, urllib3, idna, anyio, pydantic, PyYAML und click.
- Browser-Bibliotheken aktualisiert: hls.js 1.6.16 → 1.7.4 und MapLibre GL JS
  5.8.0 → 5.24.1.

### Removed

- Ungenutzte Module `core/logging.py` und `stream/filter_request.py`.
- Wirkungslose CSS-Regeln für die frühere Kopfzeile und Seitenleiste
  (rund 460 Zeilen).

---

## [0.18.0] - 2026-11-24

### Added

- Dunkelmodus für die gesamte Oberfläche und die Anmeldeseite. Er folgt
  automatisch der Systemeinstellung und lässt sich im Benutzermenü fest auf
  Hell oder Dunkel stellen.
- Ladeanzeige in den Videokacheln, bis das erste Bild eines Livestreams da
  ist.

### Changed

- Neue, ruhigere Oberfläche:
  - Die Seitenleiste sitzt fest am linken Rand und lässt sich auf Symbole
    einklappen; auf Tablets zeigt sie nur Symbole, auf Smartphones bleibt sie
    als Leiste am unteren Rand.
  - Die Kopfzeile zeigt links den Seitentitel und rechts Uhrzeit, Status und
    ein Benutzermenü mit Abmelden.
  - Statt der dunklen Statuskapseln (Quelle, Encoder, Streaming, CPU, RAM,
    Temperatur) gibt es eine einzige Anzeige „Einsatzbereit“ bzw. „Störung“.
    Admins sehen die Details per Klick; die Temperatur erscheint nur, wenn
    ein Sensor vorhanden ist.
  - Einheitliche Linien-Symbole in Navigation und Einstellungen statt
    gemischter Schriftzeichen und Emojis.
  - Einheitliche Abstände, Ecken, Schatten und Kartenüberschriften.
- Die Karte nutzt auf großen Bildschirmen die volle verfügbare Fensterhöhe
  statt fest 520 Pixel; auf Smartphones belegt sie 70 % der Höhe.

### Removed

- Nicht mehr genutzte Stylesheets `header.css` und `sidebar.css` sowie die
  alte, ungenutzte Funktion zum Ausblenden der Seitenleiste.

---

## [0.17.3] - 2026-11-24

### Changed

- Die Eingabefelder der Anmeldeseite sind schmaler und schlichter gestaltet
  und ragen nicht mehr über den Button hinaus.

---

## [0.17.2] - 2026-11-24

### Changed

- Die Kartenebenen sind beim Öffnen der Karte zunächst eingeklappt.

---

## [0.17.1] - 2026-11-24

### Fixed

- Beim Abspielen eines Livestreams erschien im Browser ein Anmeldefenster und
  das Bild lief stockend oder brach ab. MediaMTX sendet bei einigen
  Leseanfragen (WebRTC-Verbindungsaufbau, HLS-Startseite) eine leere
  Sitzungs-ID, die die Anmeldeprüfung von Open BOS Stream fälschlich als
  ungültige Anfrage abwies.
- Der Browser sendet das Medien-Token jetzt immer mit, auch über HTTPS. Eine
  Ablehnung löst damit nie mehr den Anmeldedialog des Browsers aus.
- Abgelehnte Leser werden mit ihrer Adresse protokolliert.

---

## [0.17.0] - 2026-11-22

### Security

- Livebilder lassen sich nicht mehr ohne Anmeldung abrufen. Bisher erlaubte
  MediaMTX jedes Lesen ohne Rückfrage, sodass Streams z. B. über den offenen
  RTMP-Port 1935 oder ohne HTTPS über die Ports 8888/8889 abspielbar waren.
  Lesen ist nun nur noch auf dem Server selbst (Caddy nach Sitzungsprüfung,
  interne Prozesse, lokales Display) oder im Browser mit einem kurzlebigen
  Medien-Token aus der Anmeldung erlaubt.
- Die Ersteinrichtung verlangt einen einmaligen Einrichtungscode. Ein frisch
  installierter Server kann dadurch nicht mehr von Fremden übernommen werden.
  Der Installer zeigt den Code an; er steht auch im Journal.
- Das Sitzungscookie trägt hinter HTTPS das Attribut `Secure`. Der Installer
  warnt, wenn ein Server ohne HTTPS betrieben wird.
- Nur noch Superadmins dürfen die Gesamtkonfiguration speichern. Admins
  konnten darüber bisher z. B. die automatische Bereinigung einschalten und
  so Aufnahmen löschen lassen; sie speichern nun ausschließlich Quellen.
- Admins sehen die Ziel-URLs der Streaming-Ausgänge nur noch maskiert, ohne
  Stream-Schlüssel.
- Jeder API-Endpunkt deklariert seine Mindestrolle selbst. Ein Test schlägt
  fehl, wenn eine Route ohne Rolle hinzukommt; neue Endpunkte sind dadurch
  nicht mehr versehentlich für Zuschauer offen.
- uvicorn wertet Weiterleitungs-Header nur noch hinter Caddy aus. Über den
  lokalen Port-80-Proxy ließ sich die Anmeldesperre bisher mit gefälschten
  Adressen umgehen; zugleich sperrt dort die IP-weite Grenze nicht mehr alle
  Geräte auf einmal aus.
- Abmelden macht die Sitzung serverseitig ungültig, statt nur das Cookie zu
  löschen.

### Added

- Streaming-Ausgänge unterstützen neben RTMP und SRT nun auch RTSP.
- Die Anmeldeseite verlinkt eine einseitige Funktionsübersicht der Software
  als PDF („Was ist Open BOS Stream?“). Sie ist ohne Anmeldung abrufbar; die
  Druckvorlage liegt unter `docs/funktionsuebersicht.html`.

### Changed

- `requirements.txt` enthält nur noch Laufzeitpakete; Testwerkzeuge stehen
  in `requirements-dev.txt`. `pyproject.toml` nennt `requests` als
  Abhängigkeit. Nicht genutzte Pakete (`pydantic-settings`,
  `python-dotenv`) wurden entfernt.
- Die CI prüft zusätzlich JavaScript-Syntax und einheitliche Formatierung
  von JavaScript, CSS und Templates.
- Benutzerdaten und Kartenkonfiguration werden nicht mehr bei jeder Anfrage
  neu von der Festplatte gelesen.
- Die Git-Historie wurde bereinigt: Ein früher versehentlich eingecheckter
  Stream-Schlüssel ist aus allen Commits und Tags entfernt. Bestehende Klone,
  etwa auf dem Server, müssen einmalig mit
  `git fetch origin && git reset --hard origin/main` angeglichen werden, da
  `update.sh` sonst beim `git pull --ff-only` abbricht.

### Deprecated

- Konfigurationsdateien im Format vor Version 0.11 (`capture`/`input` als
  Einzelstream, `rtmp_inputs`) werden weiterhin eingelesen, erzeugen aber
  eine Warnung im Journal. Version 1.0 liest sie nicht mehr; ein einmaliges
  Speichern der Einstellungen überführt sie ins aktuelle Format.

### Removed

- Nicht mehr verwendeter Code der früheren Einzelstream-Ansicht
  (`dashboard_stream.js` und fünf ungenutzte Templates) sowie doppelte
  Kartenfunktionen.

---

## [0.16.2] - 2026-10-09

### Changed

- In der Karte sind nun alle Ebenen standardmäßig eingeblendet, auch die
  dipul-Gruppen Verkehrswege, Einrichtungen und Sonstiges. Einzelne Ebenen
  lassen sich weiterhin im Menü „Kartenebenen“ ausblenden.

---

## [0.16.1] - 2026-10-09

### Fixed

- Die Oberfläche ist auf Smartphones und Tablets besser lesbar:
  - Die Kopfzeile passt auf schmale Bildschirme; Rolle und das Wort
    „Einsatzbereit“ werden bei Platzmangel ausgeblendet, die Uhrzeit bleibt
    vollständig sichtbar.
  - Lange Quellennamen und Profile wie `copy_repair_low_latency` brechen um,
    statt den Online-/Offline-Status zu überdecken oder aus der Kachel zu
    laufen. Offline-Quellen stehen auf Smartphones untereinander.
  - Der Medienbalken bricht Quelle und Aufnahmeart sauber um und bleibt
    innerhalb seiner Karte.
  - Das Ereignisprotokoll bricht seinen Kopf um und wächst mit seinem
    Inhalt, statt eine feste Höhe zu belegen.
  - Die Schaltflächen zum Sortieren und Entfernen von Quellen in den
    Einstellungen stehen auf Smartphones unter dem Quellennamen.
  - Auf Tablets passt die Systemzeile in der Kopfzeile in eine Zeile.

---

## [0.16.0] - 2026-10-09

### Added

- Die Karte zeigt optional die Drohnen-Geozonen der Digitalen Plattform
  Unbemannte Luftfahrt (dipul) an, in sieben ein- und ausschaltbaren
  Gruppen: Luftraum, temporäre Einschränkungen, Schutzgebiete und
  Infrastruktur sind standardmäßig sichtbar, Verkehrswege, Einrichtungen
  und Sonstiges lassen sich zuschalten.
- Ein Klick auf die Karte zeigt die dort geltenden Geozonen mit Name, Art,
  Höhenbegrenzung und Rechtsgrundlage.
- Die Kartenbilder werden über den eigenen Server abgerufen und eine Stunde
  zwischengespeichert. Ist dipul nicht erreichbar, weist die Karte darauf
  hin. Die Quellenangabe „© dipul (DFS), CC BY-ND 4.0“ und ein Hinweis zur
  fehlenden Rechtsverbindlichkeit stehen direkt unter der Karte.

---

## [0.15.3] - 2026-10-08

### Changed

- Die Ansicht für Zuschauer ist aufgeräumt: Die obere Statusleiste mit
  Quelle, Encoder, Streaming, CPU, RAM und Temperatur, das
  Ereignisprotokoll sowie technische Angaben an den Livebildern
  (Protokoll und Verarbeitungsprofil, Empfangsadresse, Auflösung/Codec,
  Viewerzahl und Hauptstream-Zustand) werden Zuschauern nicht mehr
  angezeigt. Ein hinterlegter Drohnen-Typ erscheint stattdessen unter dem
  Quellennamen. Admins und Superadmins sehen weiterhin alle Angaben.
- Die Rolle wird in der Kopfzeile auf Deutsch angezeigt (Zuschauer, Admin,
  Superadmin).
- Der Zusatz „LB“ hinter der Versionsangabe in der Seitenleiste entfällt.

---

## [0.15.2] - 2026-10-08

### Changed

- Neuinstallationen und `--install-mediamtx` ohne Versionsangabe verwenden
  nun MediaMTX 1.21.1 statt 1.19.3. Die neue Version behebt unter anderem
  hängende WebRTC-Bilder bei DJI-Drohnen, Zeitstempelfehler bei H.265 und
  verschärft mehrere Sicherheitsvoreinstellungen. Bestehende Installationen
  behalten bei normalen Updates ihre Version; ein Wechsel erfolgt weiterhin
  nur mit `--install-mediamtx`.

### Fixed

- Die verwaltete Caddyfile ist nun im Format von `caddy fmt` eingerückt. Die
  Warnung „Caddyfile input is not formatted“ beim Update entfällt; die
  Konfiguration selbst ist unverändert.

---

## [0.15.1] - 2026-10-08

### Added

- Die Systemseite zeigt unter „Anwendung & Laufzeit“ die installierte
  MediaMTX-Version an.

### Changed

- Der Speicherschutz berücksichtigt nun den Wiedergabe-Cache, in dem
  browserkompatible Kopien von Aufnahmen (z. B. aus H.265) liegen. Seine Größe
  erscheint auf der Systemseite. Unterhalb der Mindestgrenze werden zuerst
  diese jederzeit neu erzeugbaren Kopien entfernt, bevor neue Medien gesperrt
  oder Aufnahmen gelöscht werden. Kopien, die sieben Tage nicht abgespielt
  wurden, werden automatisch entfernt.

---

## [0.15.0] - 2026-10-03

### Changed

- Aufnahmen und Snapshots verwenden nun immer den Originalstream in voller
  Qualität statt der reduzierten Vorschau. Bei RTMP-Vorschauprofilen wird der
  unveränderte Publisherpfad genutzt, bei RTSP-Kameras mit Vorschau-URL der
  Hauptstream über den bedarfsgesteuerten Vollbild-Relay. Ist der Hauptstream
  nicht rechtzeitig verfügbar, wird ersatzweise die Vorschau aufgezeichnet
  und im Medienbalken darauf hingewiesen.
- H.265-Video wird bei Aufnahmen nicht mehr live nach H.264 umgewandelt,
  sondern unverändert gespeichert und für Safari/iOS als `hvc1`
  gekennzeichnet. Das vermeidet hohe CPU-Last bei 4K-Quellen; Browser ohne
  H.265-Unterstützung erhalten beim Abspielen automatisch eine kompatible
  Kopie.
- Start und Stopp von Aufnahmen sowie das Erstellen von Snapshots blockieren
  die übrige Weboberfläche nicht mehr.

---

## [0.14.0] - 2026-10-03

### Added

- Speicherschutz für Aufnahmen und Snapshots: Unterhalb einer einstellbaren
  Warnschwelle (Standard 15 % frei) warnen Medienbalken und Systemseite.
  Unterhalb der Mindestgrenze (Standard 5 % frei) werden neue Aufnahmen und
  Snapshots gesperrt und eine laufende Aufnahme wird sauber abgeschlossen und
  gespeichert.
- Optional löscht eine automatische Bereinigung bei Speichermangel die
  ältesten Aufnahmen und Snapshots, bis wieder etwas mehr als die
  Mindestgrenze frei ist. Sie ist standardmäßig ausgeschaltet; jede Löschung
  wird protokolliert und die letzte Bereinigung auf der Systemseite angezeigt.
- Superadmins können Aufnahmen und Snapshots in der Mediathek als „Behalten“
  markieren. Markierte Medien werden nie automatisch gelöscht.
- Die Einstellungen für den Speicherschutz werden separat und ohne Neustart
  des Streamers gespeichert.

---

## [0.13.0] - 2026-10-03

### Added

- Superadmins können die Aufnahme der ausgewählten Medienquelle zwischen
  manueller und automatischer Steuerung umschalten. Im Automatikmodus beginnt
  die Aufnahme beim Eintreffen des Signals und wird bei dessen Ende sauber
  abgeschlossen; die Steuerung läuft serverseitig ohne geöffneten Browser.
- Der Schalter für die Aufnahmeart wird nun unmittelbar über einen eigenen
  Endpunkt gespeichert. Dafür wird weder die gesamte Streamkonfiguration
  aktiviert noch der Streamer neu gestartet; Erfolg und Fehler erscheinen
  direkt am Schalter und ein fehlgeschlagener Wechsel wird sichtbar
  zurückgenommen.

### Security

- Die automatische Viewer-Anmeldung des lokalen Kiosk-Displays verlangt nun
  zusätzlich ein geheimes Ticket, das der Display-Dienst bei jedem Start neu
  erzeugt und nur für das Dienstkonto lesbar ablegt. Bisher genügte im
  lokalen Profil ein Aufruf von `/?display=1` über Port 80, weil der
  Port-80-Proxy alle Anfragen scheinbar von `127.0.0.1` weiterleitet; damit
  konnten Geräte im Netzwerk ohne Anmeldung Live-Streams sehen. Im
  Protokoll des Display-Dienstes wird das Ticket unkenntlich gemacht.

---

## [0.12.1] - 2026-08-21

### Changed

- Die bereinigte Stream-Logansicht auf der Systemseite ist nun neben
  Superadmins auch für normale Admins verfügbar. Der Server-Neustart bleibt
  weiterhin ausschließlich Superadmins vorbehalten.

### Fixed

- Laufende Aufnahmen werden nun unabhängig vom Dashboard überwacht. Bei einem
  Streamabbruch wird eine gültige MP4-Teilaufnahme automatisch abgeschlossen,
  validiert und in der Mediathek veröffentlicht; beschädigte Teilaufnahmen
  werden entfernt und als Fehler gemeldet. Ein wiederkehrender Stream startet
  weiterhin keine unbeabsichtigte Folgeaufnahme.

## [0.12.0] - 2026-08-20

### Added

- Superadmins können auf der Systemseite ein automatisch aktualisiertes,
  serverseitig bereinigtes Stream-Protokoll von Open BOS Stream, dem Streamer
  und MediaMTX einsehen. Es enthält insbesondere eingehende Verbindungen,
  Authentifizierungsfehler und Streamparameter, ohne Tokens oder URL-Passwörter
  offenzulegen.
- Ein doppelt bestätigter Systemseiten-Befehl kann den Server zeitversetzt neu
  starten. Protokollzugriff und Neustart verwenden fest definierte, root-eigene
  Helfer und sind in Oberfläche und API ausschließlich Superadmins zugänglich.

## [0.11.13] - 2026-08-09

### Security

- Das verwaltete Caddy-Profil setzt HSTS, MIME-Schutz sowie restriktive
  Frame-, Referrer-, Content- und Berechtigungsrichtlinien.
- Direkte HLS- und WHEP-Zugriffe werden vor der Weiterleitung an MediaMTX
  gegen die angemeldete Open-BOS-Sitzung geprüft. Unangemeldete Zugriffe auf
  bekannte Stream-Pfade werden damit abgewiesen.
- Fehlgeschlagene Anmeldungen werden protokolliert und je Benutzer/IP sowie
  IP-weit begrenzt. Wiederholte Fehlversuche führen zu einer temporären
  15-minütigen Sperre und liefern eine standardisierte Wiederholungsfrist.

## [0.11.12] - 2026-08-03

### Added

- Für jeden RTMP- oder SRT-Streaming-Ausgang kann nun explizit ausgewählt
  werden, welche der konfigurierten Quellen weitergeleitet wird. Bestehende
  Ausgänge übernehmen rückwärtskompatibel die bisher verwendete erste aktive
  Quelle; Statusanzeige und Startprüfung beziehen sich anschließend auf die
  ausgewählte Quelle.
- Admins können Viewer- und Admin-Konten anlegen, bearbeiten und entfernen.
  Superadmin-Konten bleiben für sie sowohl in der Oberfläche als auch über
  direkte API-Aufrufe vollständig geschützt; nur Superadmins dürfen diese
  Konten sehen oder verwalten und weitere Superadmins anlegen.

### Fixed

- HEVC-Aufnahmen werden beim Stoppen nicht mehr allein wegen tolerierbarer
  Decoderwarnungen oder des FFmpeg-SIGINT-Exitcodes verworfen. Die erzeugte
  MP4-Datei wird inhaltlich validiert; außerdem kann eine große Menge an
  FFmpeg-Fehlerausgaben den Aufnahmeprozess nicht mehr durch einen vollen
  Prozess-Pipe blockieren.
- Snapshots aus HEVC-Quellen warten nun auf ein vollständiges Schlüsselbild,
  ignorieren beschädigte Eingangspakete und werden erst nach erfolgreicher
  Mindestprüfung atomar in der Mediathek veröffentlicht. Dadurch gelangen
  keine grauen, nur teilweise rekonstruierten Bilder mehr in die Oberfläche.
- Der laufende Aufnahmetimer wird lokal jede Sekunde fortgeschrieben, während
  die übrigen Dashboard-Daten weiterhin nur alle zwei Sekunden abgefragt
  werden.

---

## [0.11.11] - 2026-08-03

### Changed

- Das neue Open-BOS-Stream-Signet verbindet Drohne und Flamme in einem roten
  Schutzschild auf einer dunkelblauen Kachel. Kopfzeile, Seitenleiste,
  Anmeldeseite, Favicons und installierte Web-App verwenden nun durchgängig
  dieselbe visuelle Identität.
- Die Icon-Familie enthält neben dem skalierbaren SVG passende PNG-Größen für
  Browser-Favicons, Apple-Touch-Icons sowie normale und maskierbare PWA-Icons.

---

## [0.11.10] - 2026-08-02

### Added

- Für RTMP-Quellen stehen zwei Mehrquellen-Vorschauprofile zur Verfügung:
  `ausgewogen` erzeugt maximal 854×480 Pixel bei 12 fps und etwa 1,1 Mbit/s;
  `sparsam` erzeugt maximal 640×360 Pixel bei 12 fps und etwa 800 kbit/s.
  Beide verwenden H.264 ohne Audio, skalieren kleinere Quellen nicht hoch und
  wechseln im Vollbild auf den unveränderten Originalstream.

### Changed

- Das bestehende Profil `preview_transcode` bleibt rückwärtskompatibel und
  wird nun als ausgewogene 480p-Variante behandelt. Der 360p-Sparmodus erhält
  den separaten Wert `preview_transcode_economy`.
- Direkt unter dem Mehrquellenempfang erklärt die Einstellungsseite, wann die
  ausgewogene 480p- beziehungsweise sparsame 360p-Vorschau empfohlen wird.

### Fixed

- Angemeldete Viewer dürfen den Vollbild-Hauptstream jetzt anfordern und den
  zugehörigen temporären Lease wieder freigeben. Andere schreibende Endpunkte
  bleiben weiterhin mindestens der Rolle Admin vorbehalten. Damit wechselt
  auch Edge bei einer Viewer-Sitzung von der Vorschau zum Originalstream.

---

## [0.11.9] - 2026-08-02

### Added

- RTMP-Quellen können testweise das Profil „Mehrquellen-Vorschau“ verwenden.
  Es erzeugt für die Übersicht eine WebRTC-freundliche H.264-Vorschau mit
  maximal 640×360 Pixeln, 12 fps, 800 kbit/s und ohne Audio. Das Seitenverhältnis
  bleibt erhalten, kleinere Eingangsbilder werden nicht hochskaliert und im
  Vollbild wird automatisch auf den unveränderten Originalstream gewechselt.
  Das `ultrafast`-Preset und eine einzelne FPS-Normalisierung reduzieren die
  CPU-Last gegenüber dem ersten Testprofil.

### Changed

- Der Dashboardstatus wird im Browser alle zwei Sekunden abgefragt und auf dem
  Server für 1,5 Sekunden gemeinsam zwischengespeichert. Uhr, Player-Recovery
  und Vollbildsteuerung behalten ihre bisherigen Reaktionszeiten.

### Fixed

- Safari auf dem iPhone setzt die stummgeschaltete Wiedergabe nach dem
  Verlassen des nativen Video-Vollbilds automatisch fort. Eine kurze,
  begrenzte Wiederanlaufsequenz fängt auch den von iOS verspätet ausgelösten
  Pause-Event ab, ohne die WebRTC-Verbindung unnötig neu aufzubauen.
- Blockierende Dashboard- und MediaMTX-Abfragen laufen nicht mehr im
  FastAPI-Eventloop. Gleichzeitige Browser-Polls werden kurz gebündelt und die
  Publisher-Authentifizierung nutzt die geladene Laufzeitkonfiguration. Dadurch
  laufen RTMP-Auth-Anfragen auch unter Mehrquellen- und UI-Last nicht mehr in
  den MediaMTX-Timeout.
- Aufnahmen werden zunächst außerhalb der Mediathek in eine temporäre Datei
  geschrieben, mit SIGINT sauber finalisiert und anschließend durch `ffprobe`
  validiert. Nur eine gültige MP4-Datei wird atomar in die Mediathek übernommen;
  abgebrochene oder beschädigte Aufnahmen werden verworfen.
- Die Mediathek bereitet Aufnahmen als vollständig abgeschlossene H.264/AAC-
  MP4-Dateien auf und liefert sie anschließend mit Range-Unterstützung aus.
  Damit funktioniert die Wiedergabe auch in Safari zuverlässig; während der
  einmaligen Aufbereitung zeigt der Player einen verständlichen Ladestatus.

---

## [0.11.8] - 2026-08-02

### Added

- Die Oberfläche lässt sich auf iOS und Android als eigenständige Web-App zum
  Home-Bildschirm hinzufügen. Manifest, App-Metadaten und Feuerwehr-Icons sind
  für Browser, Apple Touch Icon und maskierbare Android-Icons hinterlegt.

### Fixed

- Quellkarten zeigen im Vollbild die vom Hauptstream gemeldete Auflösung und
  Codec-Angabe. Der Vollbildknopf wechselt seine Beschriftung und beendet den
  Modus nun auch ohne Escape-Taste.
- Der Mediathek-Player unterscheidet blockiertes Autoplay von tatsächlichen
  Medienfehlern. Browserfremde Bestandsaufnahmen werden beim Abspielen über
  einen H.264/AAC-Kompatibilitätsstream bereitgestellt; neue H.265- oder
  inkompatible Audio-Aufnahmen werden bereits bei der Aufnahme konvertiert.
- RTSP-Quellen mit Vorschau-URL stellen Haupt- und Substream über getrennte
  Viewerpfade bereit. Der Hauptstream-Relay startet erst beim Vollbildaufruf,
  wird zwischen mehreren Nutzern geteilt und nach einer Nachlaufzeit wieder
  beendet. Während des Starts oder bei einem Fehler bleibt die Vorschau aktiv;
  nach dem Vollbild wechselt der Player zuverlässig dorthin zurück.

## [0.11.7] - 2026-08-02

### Fixed

- Verwaltete RTMP-Quellen warten ohne FFmpeg-Neustartschleife auf einen
  tatsächlichen Publisher und starten nach dessen Erkennung zeitnah. Ein
  fehlendes Eingangssignal erhöht weder Backoff noch Neustartzähler.
- Safari und iOS setzen ein beim Verlassen des nativen Vollbildmodus pausiertes
  Quellenvideo automatisch fort; nur bei einem fehlgeschlagenen Play-Aufruf
  wird die einzelne WebRTC-Verbindung neu aufgebaut.
- Der Server-Testmonitor maskiert Zugangsdaten in Prozesslisten und Journalen,
  bevor sie in das Testarchiv geschrieben werden.
- Die RTMP-Publisher-Authentifizierung akzeptiert Tokens sowohl im separaten
  MediaMTX-Feld als auch im Query-String älterer MediaMTX-Versionen. Ein am
  Pfad übermittelter Query-String wird vor dem Quellenvergleich entfernt;
  Ablehnungen werden ohne Ausgabe des Tokens nachvollziehbar protokolliert.

### Added

- RTSP-Quellen können eine maskierte, optionale Vorschau-URL erhalten. Für die
  Browserausgabe wird dann beispielsweise ein H.264-Substream mit 720p oder
  1080p statt des 4K-Hauptstreams verwendet.
- Quellen können das zusätzliche Profil „Copy-Reparatur · geringe Latenz“
  verwenden. Es behält die Zeitstempelkorrektur bei, reduziert den
  Eingangspuffer und begrenzt die RTSP-Verzögerung auf 100 ms. Das bestehende
  Reparaturprofil bleibt unverändert als robustere Alternative erhalten.

## [0.11.6] - 2026-08-02

### Fixed

- Viewer sehen weder die Systemseite noch deren Navigation und können die
  zugehörigen System- und Diagnose-Endpunkte nicht direkt aufrufen.
- Die Mehrquellenanzeige bleibt für Viewer aktiv, obwohl die ausschließlich
  für Admins bestimmte Systemdiagnose nicht in deren Seite gerendert wird.
- Der synthetische Testclip verwendet H.264 Baseline ohne B-Frames und ist
  damit für die WebRTC-Ausgabe geeignet. Das Publisher-Skript lehnt erkannte
  B-Frames vor einem Testlauf ab.
- Statische Software-, Betriebssystem- und Hardwareinformationen werden nur
  einmal je Anwendungslauf ermittelt. Dashboard-Polling startet daher nicht
  mehr sekündlich `ffmpeg -version` und `lsb_release`.
- Das Serverprofil fragt weder lokalen Displaydienst noch lokalen
  Port-80-Socketproxy regelmäßig ab. Erwartete negative Statusprüfungen werden
  außerdem nicht mehr als Prozesswarnung protokolliert.

### Changed

- Das RTSP-Reparaturprofil erhält einen moderaten Eingangspuffer und repariert
  Zeitstempel, ohne mit `nobuffer` und `max_delay 0` sämtliche Glättung zu
  deaktivieren.
- Öffentliches WebRTC bietet neben UDP 8189 einen TCP-Rückfallweg auf
  demselben Port. Der verwaltete UFW-Regelsatz berücksichtigt beide
  Transportprotokolle.

---

## [0.11.5] - 2026-08-02

### Added

- Ein Generator erstellt lokal einen reproduzierbaren 60-sekündigen
  H.264/AAC-Testclip mit 720p und 25 FPS, ohne Binärdateien ins Repository
  aufzunehmen.
- Ein Mehrquellen-Testwerkzeug veröffentlicht den Testclip wahlweise auf 1, 4
  oder 8 token-geschützten RTMP-Eingängen, überwacht die Publisher-Prozesse,
  protokolliert sie getrennt und beendet sie bei Abbruch kontrolliert.
- Superadmins können auf der Systemseite eine persistente Browser-Testsitzung
  starten, stoppen und als JSON exportieren. Sie erfasst alle fünf Sekunden
  System-, Quellen-, FFmpeg- und WebRTC-Werte sowie relevante Ereignisse und
  bleibt bei einem Seitenreload erhalten.
- Ein VServer-Monitor sammelt während desselben Testfensters regelmäßig
  Systemlast, FFmpeg-Prozesse und Netzwerkzähler und exportiert anschließend
  die Journale von Anwendung, Streamer, MediaMTX, Caddy und Kernel.

---

## [0.11.4] - 2026-08-02

### Added

- Jeder Quellenplayer überwacht seine WebRTC-Verbindung und den tatsächlichen
  Bildfortschritt im Browser. Empfängt der Browser weiter Pakete, dekodiert
  aber acht Sekunden lang kein neues Bild, wird nur dieser Player neu
  verbunden.
- Nach einem erkannten Quellenprozess-Neustart oder einer erfolgreichen
  serverseitigen Wiederherstellung baut der betroffene Browserplayer seine
  Verbindung gezielt neu auf.
- Die Systemseite zeigt pro Quelle die Browser-Verbindung, WebRTC-Bitrate,
  Paketverlustrate, verworfene Frames, letzten Bildfortschritt sowie Anzahl,
  Zeitpunkt und Ursache automatischer Player-Neuverbindungen.
- Automatische Player-Neuverbindungen werden im lokalen Ereignisprotokoll des
  Browsers der jeweiligen Quelle zugeordnet.
- Jede aktive Quelle kann auf der Systemseite ausdrücklich mit einer
  zweisekündigen ffprobe-Tiefendiagnose untersucht werden. Das kompakte
  Ergebnis zeigt tatsächliche Bildrate, Bitrate, Paketanzahl,
  rückwärtslaufende DTS, Jitter, maximale Paketlücke und konkrete Warnungen.
- Messergebnisse werden je Quelle für 60 Sekunden zwischengespeichert und mit
  Messzeitpunkt sowie Cachealter gekennzeichnet.

### Changed

- Player-Neuverbindungen verwenden pro Quelle einen begrenzten exponentiellen
  Backoff. Kurze Signalstatus-Schwankungen sowie ein aktiver Vollbildmodus
  lösen keinen störenden Neuaufbau aus.
- Die frühere automatische Paketdiagnose der Primärquelle wurde aus dem
  Dashboard-Polling entfernt. Eine Probe läuft nur noch nach einem bewussten
  Klick und systemweit höchstens einmal gleichzeitig.
- Die Diagnose liest den jeweiligen MediaMTX-Viewerpfad. Dadurch wird eine
  Capture Card nicht doppelt geöffnet und gemessen wird genau das Signal, das
  auch an die Browser ausgegeben wird.

---

## [0.11.3] - 2026-08-02

### Added

- Jede Quelle erhält aus Signalzustand und FFmpeg-Laufzeitwerten eine
  gemeinsame Gesundheitsbewertung: stabil, verbindet, Verarbeitung zu
  langsam, auffällige Bildfolge, hängend, Wiederherstellung oder
  Neustartschleife.
- Laufzeitstatus und Systemseite zeigen je Quelle die Neustartanzahl sowie
  die letzte Neustartursache und den Zeitpunkt des letzten Neustarts.

### Changed

- Gleichzeitige Reconnects mehrerer ausgefallener Quellen werden anhand der
  Quellen-ID reproduzierbar um bis zu 20 Prozent versetzt. Das vermeidet
  CPU-, Netzwerk- und Kamera-Lastspitzen, ohne den Backoff unkontrolliert zu
  verlängern.

---

## [0.11.2] - 2026-08-02

### Added

- Verwaltete FFmpeg-Quellen liefern maschinenlesbare Fortschrittsdaten an den
  Runner. Ein quellenbezogener Watchdog erkennt Prozesse, deren Bild- und
  Medienzeit trotz laufender PID stehen bleiben, und startet ausschließlich
  die betroffene Quelle neu.
- Der Mehrquellenstatus auf der Systemseite zeigt je verwalteter Quelle
  kompakt FPS, Verarbeitungsgeschwindigkeit, Drop-/Dup-Frames sowie das Alter
  des letzten tatsächlichen Medienfortschritts. Direkte Passthrough-Quellen
  werden eindeutig als MediaMTX-Empfang gekennzeichnet.

### Changed

- Nach 30 Sekunden stabiler Laufzeit wird der exponentielle Neustart-Backoff
  einer Quelle zurückgesetzt. Kurzzeitige alte Fehler führen dadurch nicht
  dauerhaft zu langen Wiederanlaufzeiten.
- FFmpeg läuft ohne interaktive Standardeingabe, Banner und normale
  Informationsmeldungen; Warnungen und Fehler bleiben im Journal erhalten.
  Das senkt insbesondere bei mehreren Quellen unnötige Log- und I/O-Last.
- Die passive Paketdiagnose der Primärquelle verwendet ein zweisekündiges
  Messfenster und wird für 60 Sekunden zwischengespeichert. Dadurch ist sie
  wesentlich seltener als zusätzlicher MediaMTX-Leser aktiv.
- Die kompakte Quellendiagnose zeigt zusätzlich CPU-Auslastung und
  Arbeitsspeicher des jeweiligen FFmpeg-Prozesses.

---

## [0.11.1] - 2026-08-01

### Added

- Superadmins können eine aktive Quelle als Snapshot- und Aufnahmequelle
  festlegen. Ein kompakter Balken über den Livebildern bietet Snapshot sowie
  Aufnahme Start/Stopp mit laufendem Timer; neue Dateien erscheinen weiterhin
  in der bestehenden Mediathek und tragen die Quellen-ID im Dateinamen.
- Die Systemseite zeigt einen leichtgewichtigen Mehrquellenstatus mit Profil,
  Signal, Codec, Auflösung, Viewerzahl und optionalem Drohnen-Typ für jede
  aktive Quelle.

### Changed

- Die tiefe Prozess-, Zeitstempel- und Playerdiagnose ist eindeutig als
  Diagnose der namentlich angezeigten Primärquelle gekennzeichnet.

### Fixed

- Der Webzugriffsstatus auf der Systemseite verwendet im Serverprofil die
  Caddy-/HTTPS-Konfiguration statt der lokalen, privilegierten Port-80-API.
- Die CPU-Auslastung wird fortlaufend zwischen Dashboard-Aktualisierungen
  gemessen. Fehlende Temperatursensoren auf vServern erscheinen als „nicht
  verfügbar“ statt als irreführende `0 °C`; weitere Linux-Sensornamen werden
  unterstützt.
- Installationsprofil, öffentliche Domain, HTTPS-, WebRTC- und Firewall-Modus
  stammen auf der Systemseite nun aus demselben Host-Metadatenpfad wie in der
  System-API; Serverinstallationen werden korrekt dargestellt.
- Die Admin-Oberfläche ruft beim Start keine ausschließlich für Superadmins
  geladenen Medien- und Snapshot-Funktionen mehr auf. Dadurch wird die
  Quellenkonfiguration für Admins vollständig initialisiert.

## [0.11.0] - 2026-08-01

### Added

- Jede Quelle besitzt in den Einstellungen das optionale Textfeld
  „Drohnen-Typ“ für die Dokumentation des eingesetzten Modells.
- Der Installer legt einen fehlenden unprivilegierten Dienstbenutzer und seine
  Gruppe bei Neuinstallationen automatisch an.
- Dienstbenutzer und Gruppe können mit `--service-user` und
  `--service-group` gewählt werden und werden in
  `/etc/open-bos-stream/install.env` gespeichert.
- Ein eigener Admin-Endpunkt speichert ausschließlich die Quellenliste und
  lässt geschützte Systembereiche serverseitig unangetastet.

### Changed

- systemd-Units, sudoers-Regeln und Laufzeitverzeichnisse werden mit der
  persistenten Dienstidentität erzeugt und sind nicht mehr fest an
  `streampi:video` gebunden.
- Ein direkter Root-Aufruf wird unterstützt; die Dienste selbst laufen
  weiterhin unter einem unprivilegierten Konto.
- Auf minimalen Root-Systemen funktioniert die Installation bereits vor der
  Paketinstallation ohne vorhandenes `sudo`; Benutzerwechsel erfolgen dort
  vorübergehend über `runuser`.
- Die Serverkonfiguration akzeptiert als Domain sowohl einen Hostnamen als
  auch kopierte `http://`- und `https://`-Adressen und normalisiert sie.

### Fixed

- Admins können neue und bestehende Quellen bearbeiten, speichern, sortieren
  und entfernen, ohne geschützte Superadmin-Einstellungen mitzusenden.
- Der Service-Installer erkennt den historischen Pfad
  `/home/streampi/mediamtx` auch bei direktem Aufruf und übernimmt die
  vorhandene Binärdatei atomar nach `/usr/local/bin/mediamtx`.
- Python-Paketinstallationen als Dienstbenutzer verwenden dessen tatsächliches
  Home-Verzeichnis; Root- oder sudo-Aufrufe vererben kein falsches Home mehr.
- Bei einem Wechsel des Dienstbenutzers werden vorhandene Virtualenv-Dateien
  vor dem Paketupdate auf die neue Identität übertragen.
- Der Python-Paketbau erfolgt in einer temporären, beschreibbaren Quellkopie;
  Neuinstallationen scheitern dadurch nicht mehr an root-eigenen
  `egg-info`-Metadaten unter `/opt/open-bos-stream`.

## [0.10.10] - 2026-08-01

### Added

- Der Installer kann MediaMTX optional aus den offiziellen Release-Archiven
  installieren und unterstützt `amd64`, `arm64`, `armv7` und `armv6`.
- Heruntergeladene und lokal bereitgestellte Archive werden vor der
  Installation per SHA256 geprüft.
- Neue Installeroptionen erlauben eine erzwungene Installation, eine
  bestimmte Version, ein lokales Archiv oder ausschließlich extern
  bereitgestelltes MediaMTX.

### Changed

- Der pfadgebundene RTMP-Publisher-Token gilt nun auch im lokalen
  Raspberry-Pi-Profil.
- Publisher-Tokens haben für die manuelle Eingabe an Geräten genau
  12 Zeichen und können in der Quellenkonfiguration selbst festgelegt werden.
- Bestehende längere Publisher-Tokens werden stabil auf ihre ersten
  12 Zeichen migriert.
- Der Installer verwaltet und prüft die MediaMTX-Konfiguration in beiden
  Installationsprofilen.
- Publisher-URL und Token sind auch im lokalen Profil standardmäßig verdeckt.
- MediaMTX wird unabhängig vom Home-Verzeichnis unter
  `/usr/local/bin/mediamtx` betrieben. Bestehende Altinstallationen werden
  automatisch dorthin migriert.
- Die systemd-Unit verwendet ein eigenes Arbeitsverzeichnis unter
  `/var/lib/open-bos-stream` und startet nur nach Fehlern automatisch neu.
- Die Login- und Ersteinrichtungsseite zeigt die Produktidentität mit
  Feuerwehr-Icon, Anwendungsname und einer kurzen Beschreibung deutlicher und
  ist für kleine Bildschirme kompakter gestaltet.

### Security

- Externe RTMP-Publisher müssen unabhängig vom Installationsprofil die
  passende Kombination aus Quellen-ID und Token verwenden.

### Fixed


## [0.10.9] - 2026-07-30

### Added

- Jede RTMP-Quelle erhält im Serverprofil einen eigenen, persistenten
  Publisher-Token.
- Die Einstellungen zeigen die vollständige RTMP-Empfangsadresse im Format
  `rtmp://server.example:1935/quelle-1?token=GEHEIMNIS` standardmäßig
  verdeckt und erlauben das gezielte Einblenden.

### Changed

- Die Seite „Medien“ und ihre API-Endpunkte sind ausschließlich für
  Superadmins verfügbar.
- Vorhandene Snapshot- und Aufzeichnungsfunktionen bleiben unverändert und
  werden vorerst nicht weiter ausgebaut.

### Security

- MediaMTX authentifiziert externe RTMP-Publisher im Serverprofil per
  HTTP-Callback gegen Quellen-ID und Token.
- RTMP bleibt trotz Publisher-Token unverschlüsselt; VPN oder RTMPS bleiben
  als spätere Transportabsicherung vorgesehen.

## [0.10.8] - 2026-07-30

### Added

- Der Installer bietet die persistenten Profile `local` und `server`; das
  Server-Profil verzichtet auf Capture- und Display-Abhängigkeiten.
- Optionale Caddy-Installation mit automatischen Let's-Encrypt-Zertifikaten.
- HTTPS-Routen für Anwendung, WHEP und HLS unter derselben Domain.
- Öffentliche WebRTC-Konfiguration mit Domain und UDP-Port 8189.
- Optionale UFW-Konfiguration mit Erkennung und Erhalt des SSH-Ports.
- Persistente Serverparameter und nicht-interaktive Installeroptionen.
- Die Systemseite zeigt Installationsprofil, öffentliche Domain, HTTPS-,
  WebRTC- und Firewall-Modus.

### Changed

- Capture-Quellen und das lokale Display werden im Server-Profil nicht
  angeboten.
- Der Browser verwendet unter HTTPS relative WHEP- und HLS-Adressen, wodurch
  keine Mixed-Content-Anfragen entstehen.
- RTMP-Empfangsadressen verwenden im Server-Profil die konfigurierte
  öffentliche Domain.
- Bei aktiviertem HTTPS lauschen Uvicorn, HLS, WHEP, RTSP und MediaMTX-API
  ausschließlich lokal.

### Security

- RTMP auf Port 1935 bleibt vorerst bewusst unverschlüsselt und ohne
  Authentifizierung; Dokumentation und Oberfläche weisen darauf hin.
- UFW-Regeln werden nur nach expliziter Auswahl angewendet und halten den
  erkannten SSH-Port offen.

## [0.10.7] - 2026-07-30

### Changed

- Die wirkungslose globale Karte „Bereitstellung / Wiedergabe“ wurde aus der
  Mehrquellen-Konfiguration entfernt.
- Die separate globale Transcoding-Karte wurde entfernt. Encoder, Bitrate,
  Pixelformat, GOP, Preset und Tune befinden sich direkt in der jeweiligen
  Quelle und erscheinen nur beim Profil „Transcodieren“.
- Benutzerkonten lassen sich aufklappen und bearbeiten.

### Added

- Superadmins können Rollen bestehender Benutzer ändern.
- Superadmins können für bestehende Benutzer ein neues Passwort setzen.
- Rollen- und Passwortänderungen machen bestehende Sitzungen des betroffenen
  Benutzers ungültig.
- Verfügbare Encoder werden passend zum Quellentyp jeder Transcoding-Quelle
  ermittelt.

### Security

- Der letzte Superadmin kann weder gelöscht noch zu einer niedrigeren Rolle
  herabgestuft werden.

## [0.10.6] - 2026-07-30

### Fixed

- Eine bewusst leere Quellenliste bleibt nach dem Speichern leer und löst
  nicht erneut die Migration der alten Standardquelle aus.
- Blockierende Vorabprüfungen und systemd-Aufrufe laufen außerhalb des
  FastAPI-Eventloops; Status- und Browseranfragen bleiben dabei ansprechbar.
- Das Entfernen der letzten verwalteten Quelle stoppt den Streamer kontrolliert,
  ohne ihn anschließend erneut zu starten.

### Changed

- Der Speicherdialog erklärt, dass Aktivierung und Dienstwechsel einige
  Sekunden benötigen können.
- Konfigurationsanfragen brechen nach 35 Sekunden mit einer verständlichen
  Fehlermeldung ab, statt unbegrenzt im Ladezustand zu bleiben.
- Offline-Quellen werden kompakt und gesammelt unter den aktiven Playern
  dargestellt.
- Die Oberfläche verwendet die drei Rollen Viewer, Admin und Superadmin.

### Added

- Lokale Ersteinrichtung des ersten Superadmins, Anmeldung, Abmeldung und
  signierte Sitzungscookies.
- Lokale Benutzerverwaltung für Superadmins mit PBKDF2-Passwort-Hashes.
- Serverseitige Rollenprüfung für alle schreibenden API-Zugriffe.
- Streaming-Ausgänge, lokales Display, Webzugriff, Benutzerverwaltung und das
  Wiederherstellen einer Gesamtkonfiguration sind Superadmins vorbehalten.
- Admins können Quellen verwalten, ohne geschützte Systemfelder verändern zu
  können.
- Die Installationsprüfung verwendet den öffentlichen Auth-Status und bleibt
  dadurch auch vor dem Anlegen des ersten Superadmins funktionsfähig.
- Gespeicherte Navigation auf eine nun rollenbedingt unsichtbare Seite fällt
  automatisch auf die Übersicht zurück.
- Der lokale Kiosk erhält automatisch eine ausschließlich über Loopback
  gültige Viewer-Ansicht; der normale Displaymodus verlangt eine Anmeldung.

## [0.10.5] - 2026-07-30

### Changed

- Quellenoptionen sind in kompakte, aufklappbare Zeilen zusammengefasst.
- Audio ist bei neuen Quellen standardmäßig deaktiviert und wird ausschließlich
  in der Quellenkonfiguration eingestellt.
- RTSP- und andere geschützte Quelladressen lassen sich bewusst einblenden,
  bearbeiten und anschließend wieder maskieren.
- Statusaktualisierungen verschieben bestehende Player nicht mehr im DOM.
- Kurze Statusaussetzer erhalten den laufenden Player vier Sekunden lang,
  anstatt die WebRTC-Verbindung sofort zu beenden.

### Fixed

- Vollbild wurde durch das periodische Neu-Einhängen der Quellenkarte sofort
  wieder beendet.
- Der Safari-/iPad-Fallback wird jetzt auch versucht, wenn Karten-Vollbild
  vorhanden ist, aber vom Browser abgelehnt wird.

## [0.10.4] - 2026-07-30

### Added

- Jede Quellenkachel besitzt einen eigenen Vollbild-Schalter.
- Der Vollbildmodus nutzt die native Element-API und auf Safari/iPad den
  dort verfügbaren Video-Vollbildmodus als Rückfall.

## [0.10.3] - 2026-07-30

### Changed

- Alle Mehrquellen-Player starten ausdrücklich und browserübergreifend stumm.
- Jede Quellenkachel besitzt einen eigenen Schalter, um ihren Ton bewusst
  ein- oder wieder auszuschalten.

## [0.10.2] - 2026-07-30

### Added

- Quellen können in den Einstellungen mit Hoch-/Runter-Schaltflächen
  umsortiert werden; die Reihenfolge gilt unmittelbar für das Livebildraster.
- Das Ereignisprotokoll erfasst Signal verfügbar/verloren,
  Viewer-Verbindungen und deaktivierte oder entfernte Quellen für jeden
  konfigurierten Stream.

### Changed

- Das Dashboard verwendet ausschließlich das einheitliche Livebildraster.
- Der alte große Einzelstream-Player sowie die überholten Karten
  „Übersicht“ und „Stream“ wurden entfernt.
- Die initiale Ereignismeldung zeigt die Anzahl online verfügbarer Quellen.

### Fixed

- Die globale Playerinitialisierung funktioniert auch auf dem Dashboard ohne
  das entfernte Einzelstream-Videoelement.
- Bereits gerenderte Livebildkarten übernehmen nach einer Umsortierung
  zuverlässig die gespeicherte Quellenreihenfolge.
- Beim Entfernen einer Quellenkarte wird auch ihr Diagnose-Timer beendet.

## [0.10.1] - 2026-07-30

### Added

- Die Kartenansicht zeigt bei fehlendem Kartenmaterial einen verständlichen
  Installationshinweis mit Download-Link für die Karte des Landkreises Stade.
- Der tatsächlich konfigurierte Zielpfad der MBTiles-Datei wird direkt in der
  leeren Kartenansicht angezeigt.
- Die Installationsdokumentation beschreibt Download, Dateiname,
  Berechtigungen und den Standardpfad
  `/opt/open-bos-stream/mapdata/stade.mbtiles`.

### Changed

- Neuinstallationen verwenden für Kartendaten konsistent den produktiven
  Laufzeitpfad `/opt/open-bos-stream/mapdata`.

## [0.10.0] - 2026-07-30

### Added

- Einheitliche Verwaltung von bis zu acht gleichwertigen Quellen.
- Unterstützung aller vorhandenen Quellentypen in der Quellenliste:
  Capture Card, RTMP, RTSP, SRT, UDP, HTTP und HLS.
- Pro Quelle auswählbare Profile für direkten Stream Copy,
  Zeitstempelkorrektur und Transcoding.
- Pro Quelle wählbare Audioübernahme, AAC-Transcoding oder deaktiviertes Audio.
- Direkter RTSP-Pull für Netzwerkkameras einschließlich TCP-/UDP-Auswahl.
- Unabhängige Wiedergabepfade, Statusprüfung und WebRTC-Kacheln pro Quelle.
- systemd-überwachter Mehrquellen-Supervisor mit unabhängigen
  Wiederverbindungsversuchen und begrenztem Backoff.

### Changed

- Die bisherige Standardquelle und zusätzliche RTMP-Slots werden automatisch
  in eine gemeinsame Quellenliste migriert.
- RTMP-Empfangspfade werden unveränderlich aus der Quellen-ID erzeugt:
  `rtmp://<StreamPi-IP>:1935/<id>`.
- Quellen-IDs akzeptieren ausschließlich Kleinbuchstaben, Zahlen,
  Bindestriche und Unterstriche.
- Die Einstellungen zeigen keine separate Hauptquelle mehr; Encoderparameter
  gelten nur noch als Vorgabe für Quellen mit Transcoding-Profil.
- Dashboard-Player werden ausschließlich für tatsächlich verfügbare Quellen
  geöffnet.

### Fixed

- Eine ausgefallene oder noch nicht sendende Quelle beendet nicht mehr die
  Verarbeitung aller übrigen Quellen.
- HTTP- und HLS-Quellen akzeptieren wieder korrekt `http://` und `https://`.
- Zugangsdaten in Netzwerk-URLs und sensible URL-Parameter werden in
  Streamer-Protokollen redigiert.
- Fehlende lokale V4L2-Erkennung blockiert nicht mehr die Konfiguration
  anderer Quellentypen.

## [0.9.2] - 2026-07-30

### Fixed

- Der Button „RTMP-Eingang hinzufügen“ legt wieder unmittelbar einen
  konfigurierbaren Eingang an.
- Konfigurierte RTMP-Eingänge werden in den Einstellungen und im
  Mehrquellen-Dashboard wieder zuverlässig gerendert.
- Die gemeinsame HTML-Escaping-Funktion steht vor allen abhängigen
  Mehrquellen-Skripten zur Verfügung.

## [0.9.1] - 2026-07-30

### Fixed

- Die lokale Laufzeitkonfiguration `config/stream.yaml` wird nicht mehr von
  Git verwaltet und kann Updates daher nicht mehr blockieren.
- Neuinstallationen erzeugen die Laufzeitkonfiguration einmalig aus
  `config/stream.example.yaml`; vorhandene Einstellungen bleiben unangetastet.
- Die mitgelieferte Beispielkonfiguration enthält keine Zieladressen oder
  Zugangsdaten für externe Streaming-Ausgänge.

## [0.9.0] - 2026-07-30

### Added

- Konfigurierbare Mehrquellenverwaltung für bis zu acht RTMP-Eingänge.
- Individuelle Namen, IDs, Publisher-Pfade und optionale separate
  Wiedergabepfade pro Eingang.
- Gemeinsame MediaMTX-Statusprüfung aller Eingänge mit Online-, Codec-,
  Auflösungs- und Viewerstatus.
- Dynamisches Dashboard-Raster mit einer unabhängigen WebRTC-Playerinstanz
  pro tatsächlich verfügbarem Stream.
- Automatische Migration des bisherigen einzelnen RTMP-Eingangs in den
  ersten Mehrquellen-Slot.

### Changed

- Die bisherige Einzelstreamanzeige wird bei konfigurierten RTMP-Slots durch
  das Mehrquellenraster ersetzt.
- Offline-Eingänge öffnen keine Browser-Medienverbindung und zeigen nur ihre
  individuelle Empfangsadresse.
- Aufnahmefunktionen werden nicht in den neuen Mehrquellen-Workflow
  übernommen.

## [0.8.9] - 2026-07-30

### Fixed

- Der RTMP-Reparaturpfad begrenzt die FFmpeg-Interleave-Wartezeit von
  standardmäßig bis zu zehn Sekunden auf 100 ms.
- RTSP-Eingang und RTSP-Ausgabe arbeiten im Reparaturmodus mit
  reduziertem Puffer und sofortigem Paket-Flush.
- Der WebRTC-Wiedergabepuffer wurde auf 350 ms reduziert, um Glättung
  und einsatztaugliche Latenz besser auszubalancieren.

## [0.8.8] - 2026-07-30

### Changed

- Der WebRTC-Player verwendet einen moderaten browserseitigen
  Wiedergabepuffer, um schwankende RTMP-Zeitstempel zu glätten.
- Kurzzeitige Statusaussetzer bis sechs Sekunden beenden die laufende
  Browserwiedergabe nicht mehr.
- „Lokales Display“ steht wegen seines erhöhten Ressourcenbedarfs am
  Ende der Einstellungen.

### Fixed

- Die reine Streamanzeige verbindet sich nach einem verzögerten
  Streamausfall wieder zuverlässig.
- Der lokale Display-Dienst startet seine eigene labwc-Sitzung auch
  auf Systemen, die nur bis zur Konsole booten.
- Chromium wird nicht mehr durch eine unzulässige systemweite
  Inhibit-Anforderung am Start gehindert.

## [0.8.7] - 2026-07-29

### Added

- Neues Quellenprofil „RTMP Copy mit Zeitstempel-Reparatur“ ohne
  Videoneukodierung.
- Getrennte MediaMTX-Pfade für den ursprünglichen RTMP-Eingang und die
  stabilisierte RTSP-Ausgabe.
- Lokale MediaMTX-RTMP-Eingänge werden für die Reparatur über den
  RTSP/TCP-Spiegel gelesen, damit fehlerhafte Frame-Reihenfolgen nicht
  bereits den lokalen RTMP-Leser beenden.
- Adaptive FFmpeg-Behandlung für fehlende Zeitstempel, beschädigte
  Pakete und negative Startzeiten.
- Diagnose von Eingangsbitrate, auffälligen Paketabständen,
  Zeitstempel-Jitter und maximalen Bildlücken.
- Browserseitige WebRTC-Diagnose mit Verbindungsstatus, Paketverlust,
  Jitter, Empfangsbitrate und verworfenen Frames.

### Changed

- Die Statusanzeige unterscheidet einen instabilen Direktstream von
  einer aktiv stabilisierten RTMP-Quelle.
- Die Vorabprüfung verhindert identische MediaMTX-Ein- und
  Ausgabepfade im Reparaturmodus.

## [0.8.6] - 2026-07-29

### Fixed

- Die Tablet-Navigation reserviert im Querformat keine unsichtbare
  Bildschirmhöhe mehr. Seitenüberschrift und Inhalt schließen direkt
  an die Navigation an.

## [0.8.5] - 2026-07-29

### Added

- Optionaler Standard-Webzugriff über Port 80 mit unverändertem
  Rückfallzugang über Port 8000.
- Konfiguration und Laufzeitstatus des Webzugriffs in den Einstellungen
  sowie auf der Systemseite.
- Erkennung und verständliche Anzeige, wenn Port 80 bereits durch einen
  anderen Dienst belegt ist.
- Eigene systemd-Socket-Proxy-Units, Installationsprüfung und eng
  begrenzte sudo-Regeln für die Laufzeitsteuerung.

## [0.8.4] - 2026-07-29

### Fixed

- Konkrete FFmpeg- und SRT-Fehler werden bis zur Weboberfläche
  durchgereicht.
- Laufende Streaming-Ausgänge lesen `stderr` kontinuierlich und können
  dadurch nicht mehr an einem gefüllten Fehlerausgabepuffer blockieren.
- Bereits konfigurierte SRT-Parameter und eigene `streamid`-Werte
  bleiben erhalten und werden nicht doppelt ergänzt.
- Ein nicht konfigurierter SRT-`streamid` wird nicht mehr durch den
  festen, serverspezifischen Wert `publish:live` ersetzt.
- Früh beendete Streaming-Ausgänge liefern Exit-Ursache und
  Handlungsempfehlung.

## [0.8.3] - 2026-07-29

### Added

- Passive, gecachte Eingangsdiagnose mit `ffprobe`.
- Anzeige von Codec, tatsächlicher und nomineller Bildrate, Zeitbasis,
  B-Frames sowie geprüften Zeitstempeln.
- Erkennung unplausibler Bildraten, fehlender DTS und
  rückwärtslaufender DTS-Zeitstempel.
- Streamzustände für wartende, verbindende, stabile, instabile und
  fehlerhafte Quellen.
- Anzeige der stabilen Laufzeit und eines seit stabiler Laufzeit
  zurückgesetzten Restart-Zählers.

### Changed

- Der verwaltete Streamer verwendet systemd-Backoff von 3 bis
  60 Sekunden und ein begrenztes Startlimit.
- Der Copy-Modus erzeugt garantiert keine Videofilter oder Overlays.
- Diagnosemessungen werden höchstens alle 15 Sekunden ausgeführt.

## [0.8.2] - 2026-07-29

### Changed

- Globale Statusleiste und seitenspezifische Überschriften visuell getrennt.
- Doppelte Produktbezeichnung auf breiten Desktopansichten entfernt.
- Dashboard-Seite von „Livebetrieb“ in „Übersicht“ umbenannt.
- CPU, RAM und Temperatur werden bei mittleren Breiten kompakt
  zusammengefasst.
- Header bleibt auf Smartphone und Tablet vollständig bedienbar.

### Fixed

- Encoderabfrage bleibt auch bei fehlendem FFmpeg erreichbar.

## [0.8.1] - 2026-07-29

### Added

- Separater, zustandsloser Konfigurationstest vor dem Speichern.
- Sicherung und Wiederherstellung der letzten funktionierenden
  Konfiguration.
- Klassifizierte Streamfehler mit Zeitstempel und Handlungsempfehlung.
- Herunterladbarer System- und Streaming-Diagnosebericht.
- Warnungen für Restart-Schleifen, hohe Temperatur und knappen Speicher.
- Zentraler Prozess-Runner mit Timeout, Exit-Code, Laufzeit und Logging.

### Changed

- systemd besitzt eindeutig den Lebenszyklus von Stream- und
  Display-Dienst; FastAPI steuert und überwacht diese Dienste.
- Kurzlebige Systemaufrufe für FFmpeg, systemd, Journal, V4L2,
  Snapshots und Systeminformationen zentralisiert.
- Sensible Streamziele werden im Prozess-Logging maskiert.
- Konfigurationsdateien werden atomisch geschrieben.

## [0.8.0] - 2026-07-29

### Added

- Streaming-Diagnose mit Eingangsparametern, Encoder, Ausgabe,
  Dienstzustand, Neustartzähler und Exit-Status.
- Anzeige des letzten erkannten FFmpeg-Fehlers.
- Anzeige von freiem Speicher sowie Anzahl und Größe lokaler Medien.
- Vorabprüfung von Geräten, Berechtigungen, FFmpeg, Encodern,
  Stream-URLs und erzeugtem FFmpeg-Befehl.

### Changed

- Fehlerhafte Konfigurationen werden vor dem Speichern und Neustarten
  abgewiesen.

## [0.7.3] - 2026-07-29

### Changed

- Seitenköpfe und globale Titelzeile kompakter gestaltet.
- Abstände und Typografie für Desktop und Smartphone verdichtet.

## [0.7.2] - 2026-07-29

### Added

- Suche und Typfilter für Aufnahmen und Snapshots.
- Sichtbare Dateinamen und stabiler Auswahlzustand in der Mediathek.

### Fixed

- Medienwiedergabe wird beim Seitenwechsel sauber beendet.
- Vorschau und Mediathek werden nach Löschaktionen konsistent
  aktualisiert.

## [0.7.1] - 2026-07-29

### Changed

- Einstellungs- und Systemseite vollständig modernisiert.
- Konfiguration in klar getrennte Bereiche für Quelle, Encoder,
  Stream, Ausgänge und Display gegliedert.
- Systemdienste, Metriken und Diagnoseinformationen übersichtlicher
  dargestellt.

### Fixed

- Fehler bei der Encodererkennung unterbrechen die Statusaktualisierung
  nicht mehr.

## [0.7.0] - 2026-07-29

### Changed

- Dashboard, Navigation, Seitenköpfe und Mediathek visuell modernisiert.
- Desktop-Seitenleiste und mobile Bottom-Navigation eingeführt.
- Lade-, Leer- und Fehlerzustände vereinheitlicht.

### Fixed

- Uhrzeitaktualisierung und Medienvorschau robuster umgesetzt.

## [0.6.4] - 2026-07-29

### Fixed

- Mobile Kartenansicht und browserrelative Kartenkacheln korrigiert.
- Vorhandene Aufnahmen und Snapshots werden bei Updates aus älteren
  Laufzeitverzeichnissen übernommen.
- Medien-API verwendet konsistent das produktive Laufzeitverzeichnis.
- Fehlende Aufnahmen liefern einen korrekten HTTP-404-Fehler.

## [0.6.3] - 2026-07-28

### Fixed

- Kartenstile verwenden browserrelative Kachel-URLs und funktionieren
  dadurch auch auf entfernten Clients.

## [0.6.2] - 2026-07-28

### Fixed

- Kartenstile und Layer werden vollständig als Paketdaten installiert.

## [0.6.1] - 2026-07-28

### Fixed

- Chromium wird als Display-Abhängigkeit installiert und vom
  Installationsprüfer korrekt erkannt.
- Ein statischer, bewusst nicht beim Boot aktivierter Display-Dienst
  wird als gültig akzeptiert.

## [0.6.0] - 2026-07-28

### Added

- Verwalteter lokaler Displaybetrieb mit Wayland und labwc.
- Drei Chromium-Modi: Kiosk, normaler Browser und Vollbild-Stream.
- Start, Stopp und Status des Display-Dienstes über die Weboberfläche.
- Laufzeit-Inhibit gegen Bildschirmabschaltung und Energiesparen.

### Changed

- Display startet nur auf ausdrückliche Konfiguration und nicht
  automatisch beim Boot.
- Chromium wird nach einem Absturz durch systemd neu gestartet.

## [0.5.0] - 2026-07-28

### Added

- Atomare Quellenprofile für Capture Card und direkten
  MediaMTX-Passthrough.
- Rollback auf die vorherige Konfiguration bei fehlgeschlagener
  Aktivierung.

### Changed

- RTMP-Passthrough übernimmt kompatible Streams ohne erneute
  Videocodierung.
- Capture-Card-Änderungen werden zuverlässig in die laufenden Services
  übernommen.

## [0.4.13] - 2026-07-28

### Fixed

- Capture-Card-Konfiguration wird nach einem Profilwechsel zur Laufzeit
  korrekt angewendet.
- Streamstart nach vorherigem RTMP-Passthrough wiederhergestellt.

## [0.4.12]

### Added

- Added a unified playback state model (`idle`, `connecting`, `playing`, `error`).
- Added state change notifications for the live player.
- Added protocol-independent stream URL generation.
- Added centralized player reset handling.

### Changed

- Refactored the HTML5 live player architecture.
- Unified HLS and WebRTC playback lifecycle.
- Improved separation between playback logic and user interface.
- Moved playback state transitions to browser video events.
- Simplified player cleanup and stream switching.

### Fixed

- Fixed duplicate playback state transitions.
- Fixed duplicate resource cleanup during stream changes.
- Improved stream switching between HLS and WebRTC.

## v0.4.11

### Karten

- Dynamische Overlay-Infrastruktur für GeoJSON-Layer eingeführt.
- Unterstützung für Hydranten, Brunnen, Saugstellen sowie weitere Wasserentnahmestellen.
- Zoomabhängige Ein-/Ausblendung der Kartenebenen.
- Generische Popups für GeoJSON-Objekte.
- Standardkarte auf Stade umgestellt.
- Test-Layer `water_sources` entfernt.

## [0.4.10] - 2026-07-22

### Added
- Neuer zentraler Installer (`scripts/install.sh`) als Einstiegspunkt für die Installation.
- Automatische Installation der benötigten Systemabhängigkeiten.
- Deployment nach `/opt/open-bos-stream`.
- Initialisierung der Laufzeitumgebung (`config`, `mapdata`, `recordings`, `snapshots`).
- Automatische Erstellung und Aktualisierung der Produktions-Virtualenv.
- Installationsprüfung (`verify-installation.sh`).
- Deployment-Metadaten (`.deployment`) mit Version, Git-Commit und Installationszeitpunkt.
- Update-Skript (`update.sh`) für bestehende Installationen.
- Gemeinsame Installer-Bibliothek (`common.sh`) zur Zentralisierung von Pfaden und Hilfsfunktionen.

### Changed
- Installationsprozess vollständig modularisiert.
- systemd-Service nutzt nun den Python-Interpreter der Produktions-Virtualenv (`python -m uvicorn`).
- Deployment schützt Konfigurations- und Laufzeitdaten vor dem Überschreiben.
- Laufzeitverzeichnisse werden automatisch erstellt und mit den korrekten Besitzrechten versehen.
- Deployment-Version wird direkt aus `src/open_bos_stream/version.py` gelesen.

### Fixed
- Installation funktioniert jetzt auch auf Systemen ohne vorinstalliertes `pip`.
- Konsistente Initialisierung der Produktionsumgebung.
- Mehrere Duplikate und redundante Pfaddefinitionen in den Installationsskripten entfernt.
- Versehentlich eingecheckte temporäre Dateien aus dem Repository entfernt.

## v0.4.9-2 - Overlay Architektur Refactoring - 2026-07-20

### Added
- zentraler Overlay-Manager für Kartenebenen
- dynamische Overlay-Registry
- automatische Layer-Erzeugung aus Konfiguration
- dynamische Layer-Controls

### Changed
- Karteninitialisierung von Overlay-Logik getrennt
- Löschwasserquellen als erstes Registry-basiertes Overlay umgesetzt

### Technical
- neue Komponente:
  - static/js/map-overlays.js

### Basis für
- zukünftige BOS-Overlays
- Einsatzdarstellung
- Fahrzeug-/Einheitenlayer

## [0.4.9 -1] - 2026-07-20

### Added

- Added MapLibre glyph endpoint for text rendering
- Added road labels
- Added place labels
- Added optional water labels
- Added optional POI labels
- Added differentiated landuse rendering
  - parks
  - forests
  - grass
  - cemeteries
  - sports pitches

### Changed

- Switched map home location to Agathenburg
- Map center is now provided through backend configuration
- Improved MapLibre initialization using backend metadata
- Reworked road rendering
  - separate road casing
  - bridge rendering
  - tunnel rendering
- Added dedicated railway rendering
- Reduced railway line widths
- Rounded line joins and caps for smoother appearance
- Improved building rendering
- Improved water rendering
- Improved overall style consistency

### Added Styles

- New Dark map style
- Improved Basic map style

### Overlay

- Generic GeoJSON overlay architecture
- Water source overlay
- Test hydrant in Agathenburg

## [0.4.9] - 2026-07-19

### Added

- Backend-generated MapLibre styles replacing the previously static `style.json`.
- Support for multiple MapLibre style templates (currently `basic` and `dark`).
- Generic GeoJSON-based map overlay infrastructure.
- Initial `water_sources` overlay layer.
- New map API endpoints:
  - `GET /api/map/styles`
  - `GET /api/map/style?style=<name>`
  - `GET /api/map/layers`
  - `GET /api/map/layers/<name>`

### Changed

- Moved MapLibre style templates to `src/open_bos_stream/map/styles/`.
- Added dedicated overlay directory `src/open_bos_stream/map/layers/`.
- Generalized the overlay concept from `hydrants` to `water_sources`, allowing future support for hydrants, cisterns, ponds, draft points, and other firefighting water sources.
- Frontend now retrieves map styles and overlay data exclusively through the backend API.
- Map style metadata (name, attribution, bounds, center, zoom, min/max zoom) is automatically populated from MBTiles metadata.

### Internal

- Extended `MapService` with automatic style and layer discovery.
- Separated map architecture into:
  - base map styles
  - overlay layers
  - map data services
- Prepared the map subsystem for future BOS-specific overlays without coupling them to the base map style.

## [0.4.7] - 2026-07-18

### Added
- Added pluggable stream audio architecture.
- Added configurable stream audio settings.
- Added `NoneAudio` and `AlsaAudio` stream audio plugins.
- Added ALSA audio capture support for V4L2 camera streams.
- RTSP streams now support synchronized H.264 video and AAC audio.

## 0.4.6-1 (2026-07-17)

### Added

- Input-specific configuration validation before starting FFmpeg.

- `ConfigurationError` for invalid stream configurations.

### Changed

- Stream startup now returns configuration errors to the web interface.

- Stream service no longer enters a restart loop on invalid configurations.

- Improved handling when switching between different input sources.

### Fixed

- Invalid RTMP URLs are detected before FFmpeg is started.

- Stream startup displays meaningful error messages instead of silently failing.

## 0.4.6  (2026-07-17)

### Added
- RTMP input support
- Automatic encoder detection based on the selected input
- Passthrough (`copy`) encoder for network streams
- H.264 and HEVC passthrough support
- Live encoder refresh when changing inputs
- Automatic default encoder selection

### Changed
- Refactored encoder discovery
- Unified frontend encoder loading
- Improved encoder selection logic

## 0.4.5-1 (2026-07-16)

### Added
- Recording duration integrated into the live video title bar.
- Stream PID is now logged to the event log when a stream starts.

### Changed
- Simplified dashboard sidebar to navigation only.
- Moved recording and snapshot actions to the live video toolbar.
- Reduced and streamlined the application header.
- Moved version information from the header to the sidebar.
- Improved SourceManager integration across the application.
- Health service now validates the active source instead of the legacy input configuration.

### Removed
- Removed recording and snapshot sidebar cards.
- Removed PID display from the live video title bar.
- Removed obsolete templates, CSS rules and JavaScript related to the old dashboard layout.

### Fixed
- Fixed FFmpeg command generation after SourceManager migration.
- Fixed V4L2 input handling.
- Fixed several legacy references after the multi-source refactoring.

## v0.4.5 - 2026-07-16

### Added

- SourceManager zur zentralen Verwaltung von Eingangsquellen
- SourceConfig als neue Beschreibung einer Streamquelle
- InputFactory zur Erzeugung passender InputBuilder
- Unterstützung für primäre und aktive Quellen (`primary_source()`, `active_sources()`)
- Prioritätsfeld für zukünftige Quellenverwaltung vorbereitet

### Changed

- komplette Stream-Pipeline auf SourceConfig migriert
- FFmpegCommandBuilder verwendet jetzt SourceManager und InputFactory
- alle InputBuilder arbeiten mit SourceConfig statt InputConfig
- Geräte- und Encodererkennung an die neue Quellenarchitektur angepasst
- interne Streamarchitektur für mehrere Eingangsquellen vorbereitet

### Fixed

- mehrere Refactoring-Regressionen während der SourceConfig-Migration behoben
- Streamstart nach Architekturumbau wiederhergestellt
- Encoder-API an die neue Quellenarchitektur angepasst
- verbleibende Referenzen auf InputConfig und alte Variablennamen entfernt

## v0.4.4 - 2026-07-16

### Added
- DeviceManager für zentrale Geräteverwaltung
- V4L2Device-Modell
- REST API `/system/video-devices`
- automatische Erkennung unterstützter Videoformate

### Changed
- nur noch echte Video-Capture-Geräte werden angezeigt
- Encoder werden anhand der Input-Fähigkeiten gefiltert
- Encoder-Konfiguration robuster gemacht
- `config_input.js` vollständig überarbeitet
- V4L2-Erkennung modularisiert

### Fixed
- mehrere JavaScript-Fehler in der Konfiguration
- Parserfehler in `config_input.js`
- dynamische Encoderauswahl aktualisiert sich korrekt


## [0.4.3] - 2026-07-03

### Added

- Plugin-basierte Encoder-Architektur

- EncoderRegistry zur dynamischen Registrierung von Encodern

- Unterstützung für Encoder-Metadaten und konfigurierbare Encoder-Optionen

- FFmpeg Stream-Copy (`copy`) als eigener Encoder

### Changed

- Encoder vollständig von der Streamlogik entkoppelt

- Encoderoptionen werden dynamisch über die Registry bereitgestellt

- Encoderoberfläche auf dynamische Konfiguration umgestellt

### Fixed

- Mehrere Probleme bei der Auswahl und Speicherung des Encoders behoben

---

## [0.4.2] - 2026-07-01

### Added

- Plugin-basierte Input-Architektur

- InputRegistry für dynamische Eingangsquellen

- Unterstützung für V4L2-, RTSP-, RTMP-, SRT-, UDP- und HTTP-Inputs

- Dynamische Eingabefelder in der Weboberfläche

### Changed

- Stream-Inputs vollständig modularisiert

- FFmpeg-Eingänge werden durch InputBuilder erzeugt

- Vorbereitung für mehrere Videoquellen

### Fixed

- Verbesserte Behandlung dynamischer Eingabefelder

- Stabilere Konfigurationsverwaltung

---

## [0.4.1] - 2026-06-29

### Added

- Encoder-API (`/encoder`)

- Dynamische Erkennung verfügbarer FFmpeg-Encoder

- Hardware- und Software-Encoder werden unterschieden

- Unterstützung für Encoder-Fähigkeiten (Transcoding, Hardware)

### Changed

- Encoderauswahl erfolgt vollständig über die API

- Encoder werden nicht mehr statisch in der Oberfläche gepflegt

### Fixed

- Verbesserte Erkennung verfügbarer FFmpeg-Encoder

---

## [0.4.0] - 2026-06-27

### Added

- Neue modulare Streaming-Architektur

- Trennung von Input, Encoder und Output

- Registries für Stream-Komponenten vorbereitet

- Erweiterbare Stream-Pipeline

### Changed

- Große interne Umstrukturierung der Streaming-Komponenten

- Vorbereitung auf Plugin-System und zukünftige Erweiterungen

### Fixed

- Zahlreiche interne Bereinigungen und Refactorings


## [0.3.6-alpha] - 2026-06-23

### Added

- Neues Dashboard mit modernem Layout
- Modularer Videobereich
- Video-Overlay (LIVE, REC, Zuschauer, Streamtyp)
- Snapshot-Bibliothek
- Aufnahme-Bibliothek
- Ereignisprotokoll
- Systemübersicht
- Responsive Benutzeroberfläche

### Changed

- Header komplett überarbeitet
- Sidebar modernisiert
- Video-Toolbar vereinfacht
- CSS in Komponenten aufgeteilt
- Videobereich modularisiert
- Statusanzeige überarbeitet

### Fixed

- doppelte HTML-IDs entfernt
- Buttonumschaltung korrigiert
- Browser-Cache-Probleme behoben
- Responsive Layout bereinigt
- Videolayout stabilisiert
- veraltete CSS- und JavaScript-Komponenten entfernt

---

## [0.3.0-alpha]

### Initial

- Erste öffentliche Alpha-Version

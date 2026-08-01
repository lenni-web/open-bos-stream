# Changelog

Alle wichtigen Änderungen an Open BOS Stream werden in dieser Datei dokumentiert.

Dieses Projekt orientiert sich an den Empfehlungen von
"Keep a Changelog" und verwendet Semantic Versioning für Releases.

---

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

# Open BOS Stream Roadmap

Die Roadmap beschreibt die geplante Weiterentwicklung von **Open BOS Stream**.
Sie dient als Orientierung und wird bei jedem Release aktualisiert.

Der Schwerpunkt liegt auf der **Serveranwendung** (Debian-Serverprofil mit
Caddy/HTTPS, WebRTC und mehreren Netzwerkquellen). Das lokale
Raspberry-Pi-Profil mit Kiosk-Display bleibt lauffähig, wird aber nicht
funktional weiterentwickelt.

---

# Erreichter Stand (bis 0.12.x)

### Grundlage und Betrieb

- [x] FastAPI-Anwendung mit systemd-Diensten für Anwendung, Streamer und MediaMTX
- [x] Wiederholbarer Installer und Update-Mechanismus mit Installationsprüfung
- [x] Profile `local` und `server`, frei wählbares Dienstkonto
- [x] Verwaltete MediaMTX-Installation mit SHA256-Prüfung
- [x] Debian-Serverprofil mit Caddy, Let's Encrypt, öffentlichem WebRTC und UFW

### Quellen und Streaming

- [x] Bis zu acht gleichwertige Quellen (RTMP, RTSP, SRT, UDP, HTTP, HLS, Capture Card)
- [x] Stream Copy, Zeitstempel-Reparatur, Niedriglatenz-Reparatur und Transcoding je Quelle
- [x] Mehrquellen-Vorschauprofile (480p ausgewogen, 360p sparsam)
- [x] RTSP-Vorschau-URL mit bedarfsgesteuertem Vollbild-Relay
- [x] Watchdog mit unabhängigem, versetztem Backoff je Quelle
- [x] Streaming-Ausgänge mit wählbarer Quelle
- [x] Mobile Web-App (iOS/Android) und Vollbildwiedergabe

### Sicherheit

- [x] Rollen Viewer, Admin und Superadmin mit Prüfung in Oberfläche und API
- [x] Anmeldesperre gegen Durchprobieren von Passwörtern
- [x] RTMP-Publisher-Tokens je Quelle
- [x] HLS/WHEP nur für angemeldete Benutzer (Caddy `forward_auth`)
- [x] Sicherheitsheader (HSTS, CSP-Frame-Schutz, Referrer, Permissions)
- [x] Kiosk-Anmeldung nur mit geheimem Display-Ticket

### Diagnose

- [x] FPS, Geschwindigkeit, Drop-/Dup-Frames, CPU und RAM je Quelle
- [x] Gesundheitsbewertung und ffprobe-Tiefendiagnose je Quelle
- [x] Bereinigtes Stream-Protokoll für Admins, Server-Neustart für Superadmins
- [x] Browser-Testprotokoll, Mehrquellen-Lasttest und Server-Testmonitor

### Medien und Karte

- [x] Snapshots und Aufnahmen der gewählten Medienquelle mit Mediathek
- [x] Validierte, atomar veröffentlichte Aufnahmen; sichere Teilaufnahmen bei Abbruch
- [x] Automatische, signalgesteuerte Aufnahme
- [x] Offline-Karte (MapLibre, MBTiles) mit Wasserentnahmestellen-Overlays

---

# Letzte Releases

- **0.22.0** (2026-11-27): Push-Benachrichtigungen pro Gerät, Menüpunkt
  „Aufnahmen“ statt „Medien“, Seite auf Smartphones nicht mehr seitlich
  verschiebbar
- **0.21.1** (2026-11-27): Abmelden repariert, eigener Menüpunkt Organisation
- **0.21.0** (2026-11-27): Organisationen (Landkreis, Samtgemeinden, Ortswehren),
  Rollen, Fernpilotennachweise, Quellen je Wehr; eigene Seite Livebilder
- **0.20.5** (2026-11-26): Name in der Oberfläche „Open BOS Drohnen“
- **0.20.4** (2026-11-26): 24-Stunden-Vorhersage aufklappbar
- **0.20.3** (2026-11-26): Wetterseite neu sortiert, Kp-Index im Klartext,
  Erklärungen zu allen Wetterangaben
- **0.20.2** (2026-11-26): Wasser-Ebenen gruppiert (Hydranten / Unabhängige
  Löschwasserstellen), unklare Lagertanks als Ring
- **0.20.1** (2026-11-26): Wetterseite einspaltig; Taupunkt, Wolkenbasis,
  Sonnenauf- und -untergang
- **0.20.0** (2026-11-26): MapLibre 6, Online-Karte basemap.de, Luftbild
  Niedersachsen, Offline-Karte als Rückfall
- **0.19.1** (2026-11-26): Wetterseite mit Radar-Zeitleiste, Smartphone-Menü
  mit „Mehr“, Untertitel „BOS Drohnen Suite“
- **0.19.0** (2026-11-26): Wetter für den Flugbetrieb mit Ampel, DWD-Warnungen
  und Regenradar; Anleitung zur Installation als App
- **0.18.12** (2026-11-26): RTSP-Stream vom Controller über den Raspberry Pi
  weiterleiten (Vorlagen für DJI, Parrot, Skydio, Autel; Netzwerk-Skript)
- **0.18.11** (2026-11-26): Wasser-Ebenen bereinigt (keine Gülle- und
  Gastanks mehr), Bibliotheken aktualisiert, Karten-HTML abgesichert
- **0.18.10** (2026-11-26): SRT-Empfang auf dem Server, latenzarmes Senden vom
  Raspberry Pi
- **0.18.9** (2026-11-24): Dauerhaftes Ereignisprotokoll auf dem Server
  (30 Tage, für alle Admins)
- **0.18.8** (2026-11-24): Automatische Aufnahme pro Quelle, bis zu vier
  Aufnahmen parallel
- **0.18.7** (2026-11-24): Dokumentation und Funktionsübersicht aktualisiert
- **0.18.6** (2026-11-24): Uhrzeiten in deutscher Zeit statt Server-UTC
- **0.18.5** (2026-11-24): Kompakte Speichern-Leiste der Einstellungen auf
  Smartphones
- **0.18.4** (2026-11-24): Gastlinks im Ereignisprotokoll
- **0.18.3** (2026-11-24): Zeitlich begrenzte Gastlinks für ausgewählte
  Livebilder
- **0.18.2** (2026-11-24): E-Mail-Benachrichtigungen bei Störungen
- **0.18.1** (2026-11-24): MediaMTX 1.21.4, aktualisierte Python- und
  Browser-Bibliotheken, maskierte Ausgangsnamen, Aufräumarbeiten
- **0.18.0** (2026-11-24): Neue Oberfläche mit fester Seitenleiste,
  Statusanzeige, Benutzermenü und Dunkelmodus; Karte in voller Fensterhöhe
- **0.17.3** (2026-11-24): Schlankere, aufgeräumte Eingabefelder auf der
  Anmeldeseite
- **0.17.2** (2026-11-24): Kartenebenen beim Öffnen der Karte eingeklappt
- **0.17.1** (2026-11-24): Anmeldefenster und Aussetzer beim Abspielen
  von Livestreams behoben
- **0.17.0** (2026-11-22): Sicherheitshärtung (Streams nur mit Anmeldung,
  Einrichtungscode, Rollen pro Endpunkt), RTSP-Ausgänge, Funktionsübersicht
- **0.16.2** (2026-10-09): Alle Kartenebenen standardmäßig eingeblendet
- **0.16.1** (2026-10-09): Verbesserte Darstellung auf Smartphones und Tablets
- **0.16.0** (2026-10-09): Drohnen-Geozonen (dipul) in der Karte mit
  Zonenabfrage per Klick
- **0.15.3** (2026-10-08): Aufgeräumte Ansicht für Zuschauer
- **0.15.2** (2026-10-08): MediaMTX 1.21.1 als Standardversion, Caddyfile
  im `caddy fmt`-Format
- **0.15.1** (2026-10-08): Wiedergabe-Cache im Speicherschutz,
  MediaMTX-Version auf der Systemseite
- **0.15.0** (2026-10-03): Aufnahmen und Snapshots in voller Qualität des
  Originalstreams, H.265 ohne Live-Umwandlung
- **0.14.0** (2026-10-03): Speicherschutz mit Warnung, Sperre, optionaler
  Bereinigung und „Behalten“-Markierung
- **0.13.0** (2026-10-03): Automatische Aufnahme abhängig vom Eingangssignal,
  Sicherheitsfix für die Kiosk-Anmeldung

---

# Kurzfristig: Serverbetrieb absichern

### Medien

- [x] Aufnahmen und Snapshots in voller Qualität des Originalstreams

### Validierung

- [ ] Vier reale Einsatzquellen über längere Laufzeit auf dem Server validieren
- [ ] Acht Quellen im sparsamen Vorschauprofil als Belastungstest validieren

### Qualitätssicherung

- [x] Continuous Integration: Testsuite bei jedem Push auf GitHub ausführen
- [x] Release-Tags wieder konsequent setzen (ab `v0.13.0`)

### Transportsicherheit

- [x] SRT-Empfang mit Token für Sender über Mobilfunk
- [ ] Verschlüsselter Quellenempfang über RTMPS oder SRT mit Passphrase
- [ ] Latenzarmes Senden vom Raspberry Pi per SRT mit echter Hardware validieren
- [x] RTSP-Stream vom Controller über den Pi weiterleiten (Vorlagen, Netzwerk-Skript)
- [ ] RTSP-Weiterleitung mit echten Controllern validieren (Parrot, Skydio, Autel, DJI)
- [ ] Empfehlungen zur Absender-IP-Beschränkung für Port 1935 in der Oberfläche

### Speicher

- [x] Speicherplatzwarnung und Sperre neuer Medien bei Speichermangel
- [x] Optionale automatische Bereinigung der ältesten Medien bei Speichermangel
- [x] „Behalten“-Markierung für Medien, die nie automatisch gelöscht werden

---

# Mittelfristig: Betrieb und Bedienung

### Oberfläche

- [x] Feste, einklappbare Seitenleiste, Statusanzeige mit Details und Benutzermenü
- [x] Hell-/Dunkelmodus nach Geräteeinstellung oder fest gewählt
- [ ] Einsatzprotokoll-Export (Ereignisse, Aufnahmen und Snapshots eines Einsatzes)

### Konfiguration

- [ ] Vollständige Konfigurationssicherung (Export/Import inkl. Benutzer)
- [ ] Wiederherstellung über die Weboberfläche über den letzten funktionierenden Stand hinaus

### Monitoring

- [ ] Netzwerkdurchsatz und Speicherplatz auf der Systemseite im Zeitverlauf
- [x] E-Mail-Benachrichtigung bei Quellenausfall oder Systemproblemen, mit Entwarnung
- [ ] Weitere Benachrichtigungskanäle (z. B. Push über ntfy, Webhook)

### Benutzer

- [x] Zeitlich begrenzte Gastlinks für ausgewählte Livebilder, ohne Konto
- [ ] Protokoll sicherheitsrelevanter Aktionen (Anmeldung, Benutzer- und Konfigurationsänderungen)
- [ ] Optionale Zwei-Faktor-Anmeldung für Admins und Superadmins

### Karte

- [x] Drohnen-Geozonen (dipul) mit Zonenabfrage per Klick
- [ ] Weitere Overlay-Typen und eigene Marker
- [x] Wasser-Ebenen ohne Gülle-, Gas- und andere Fremdtanks
- [ ] Kartenverwaltung (MBTiles hochladen und auswählen)
- [x] Umstieg auf MapLibre 6 (ESM, WebGL2)
- [x] Online-Grundkarte basemap.de und Luftbild Niedersachsen, Offline-Karte als Rückfall
- [x] Wetter für den Flugbetrieb mit Ampel, DWD-Warnungen und Niederschlagsradar

---

# Weiterentwicklung zu „Open BOS“

Schwerpunkt bleiben Drohnen und Drohneneinsätze. Geplante Reihenfolge:

1. **0.19** Wetter und Regenradar ✔
2. **0.20** Umstieg auf MapLibre 6, Online-Grundkarte basemap.de und Luftbild ✔
3. **0.21** Datenbank (SQLite) und Organisationsmodell: Landkreis, Wehren,
   Mitglieder, Rollen je Wehr und auf Landkreisebene ✔
4. **0.22** Push-Benachrichtigungen pro Gerät ✔
5. **0.23** Einsätze: Alarmierung, Beteiligte mit Einsatzrollen, Zuordnung
   von Aufnahmen, Snapshots und Ereignissen, Einsatzbericht als PDF;
   Zusammenarbeit mehrerer Wehren, Einsatz-Gastlinks
6. **0.24** Einsatzkarte mit Quadranten: zeichnen, benennen, Status; für
   alle Beteiligten sofort sichtbar
7. **0.25+** DJI Cloud API (Pilot 2, Enterprise-Drohnen wie Matrice 30/350/4T
   und Mavic 3T): Live-Telemetrie auf der Karte, Kartenelemente und
   Quadranten in beide Richtungen
8. **1.0** Umbenennung in „Open BOS“ mit Migrationsskript, Dokumenten-Modul

---

# Langfristige Ziele

- Plugin-Schnittstellen für Overlays, Datenquellen und Ereignisse
- BOS-Erweiterungen: Sirenen, Pegelstände, Einsatzmittel
- Offiziell unterstützte Plattformen: Debian und Ubuntu Server

---

# Nicht mehr im Fokus

- Lokales Kiosk-Display (labwc/Chromium) auf dem Raspberry Pi: wird gewartet,
  aber nicht funktional erweitert.

---

# Projektvision

Open BOS Stream soll eine leichtgewichtige, einfach installierbare und modular
erweiterbare Streaming- und Kartenplattform für Behörden und Organisationen
mit Sicherheitsaufgaben (BOS) sein, die zuverlässig auf einem eigenen Server
betrieben werden kann.

Der Fokus liegt auf:

- einfacher Installation und Aktualisierung
- robustem, nachvollziehbarem Serverbetrieb
- Sicherheit und Datenschutz
- schneller Bedienung auch auf Tablets und Smartphones
- langfristiger Wartbarkeit

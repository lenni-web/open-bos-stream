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

- **0.14.0** (2026-10-03): Speicherschutz mit Warnung, Sperre, optionaler
  Bereinigung und „Behalten“-Markierung
- **0.13.0** (2026-10-03): Automatische Aufnahme abhängig vom Eingangssignal,
  Sicherheitsfix für die Kiosk-Anmeldung

---

# Kurzfristig: Serverbetrieb absichern

### Validierung

- [ ] Vier reale Einsatzquellen über längere Laufzeit auf dem Server validieren
- [ ] Acht Quellen im sparsamen Vorschauprofil als Belastungstest validieren

### Qualitätssicherung

- [x] Continuous Integration: Testsuite bei jedem Push auf GitHub ausführen
- [x] Release-Tags wieder konsequent setzen (ab `v0.13.0`)

### Transportsicherheit

- [ ] Verschlüsselter Quellenempfang über RTMPS oder SRT mit Passphrase
- [ ] Empfehlungen zur Absender-IP-Beschränkung für Port 1935 in der Oberfläche

### Speicher

- [x] Speicherplatzwarnung und Sperre neuer Medien bei Speichermangel
- [x] Optionale automatische Bereinigung der ältesten Medien bei Speichermangel
- [x] „Behalten“-Markierung für Medien, die nie automatisch gelöscht werden

---

# Mittelfristig: Betrieb und Bedienung

### Konfiguration

- [ ] Vollständige Konfigurationssicherung (Export/Import inkl. Benutzer)
- [ ] Wiederherstellung über die Weboberfläche über den letzten funktionierenden Stand hinaus

### Monitoring

- [ ] Netzwerkdurchsatz und Speicherplatz auf der Systemseite im Zeitverlauf
- [ ] Benachrichtigung bei Quellenausfall oder Systemproblemen (z. B. Webhook, E-Mail)

### Benutzer

- [ ] Protokoll sicherheitsrelevanter Aktionen (Anmeldung, Benutzer- und Konfigurationsänderungen)
- [ ] Optionale Zwei-Faktor-Anmeldung für Admins und Superadmins

### Karte

- [ ] Weitere Overlay-Typen und eigene Marker
- [ ] Kartenverwaltung (MBTiles hochladen und auswählen)

---

# Langfristige Ziele

- Plugin-Schnittstellen für Overlays, Datenquellen und Ereignisse
- BOS-Erweiterungen: Sirenen, Pegelstände, Wetterdaten, Einsatzmittel
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

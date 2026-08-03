# Open BOS Stream Roadmap

Die Roadmap beschreibt die geplante Weiterentwicklung von **Open BOS Stream**. Sie dient als Orientierung für zukünftige Funktionen und Entwicklungsziele.

---

# Version 0.11.x

## Ziel

Mehrere gleichzeitige Einsatzquellen stabil, nachvollziehbar und mit
abgestufter Ressourcenlast bereitstellen.

### Mehrquellenbetrieb

- [x] Bis zu acht gleichwertige Quellen konfigurieren und überwachen
- [x] RTMP-Publisher pro Quelle über Pfad und Token zuordnen
- [x] Originalstream im Vollbild ohne zusätzliche Transkodierung verwenden
- [x] Ausgewogene 480p-Vorschau für bis zu vier aktive Quellen
- [x] Sparsame 360p-Vorschau für viele Quellen oder knappe CPU-Reserven
- [x] FPS, Geschwindigkeit, Drop-/Dup-Frames und letzten Fortschritt anzeigen
- [x] Reproduzierbare Mehrquellen-Tests und Diagnoseexport bereitstellen
- [ ] Vier reale Einsatzquellen über längere Laufzeit validieren
- [ ] Acht Quellen im sparsamen Vorschauprofil als Belastungstest validieren

---

# Version 0.4.x

## Ziel

Stabile Basis für den produktiven Betrieb.

### Status

- [x] FastAPI-Grundgerüst
- [x] Streaming-Backend
- [x] Leaflet-Kartenintegration
- [x] Dynamisches Overlay-System
- [x] Wasserentnahmestellen
- [x] Mobile Fullscreen-Unterstützung
- [x] Produktionsbetrieb über systemd
- [x] Modularer Installer
- [x] Automatisches Deployment
- [x] Installationsprüfung

---

# Version 0.5.x

## Ziel

Ausbau der Anwendung für den täglichen Einsatz.

### Streaming

- [ ] Streamstatus
- [ ] FPS-Anzeige
- [ ] Bitratenanzeige
- [ ] Verbindungsstatus
- [ ] Stream-Neustart über WebUI

### Recorder

- [ ] Aufnahmesteuerung
- [ ] Segmentierte Aufzeichnungen
- [ ] Speicherverwaltung
- [ ] Automatische Bereinigung
- [ ] Download über WebUI

### Karten

- [ ] Weitere Overlay-Typen
- [ ] Eigene Marker
- [ ] GPS-Position
- [ ] Messwerkzeuge
- [ ] Kartenverwaltung

### Weboberfläche

- [ ] Dashboard
- [ ] Statusanzeige
- [ ] Responsive Optimierungen
- [ ] Einstellungsdialog
- [ ] Dunkles Design

---

# Version 0.6.x

## Ziel

Konfiguration vollständig über die Weboberfläche.

### Konfiguration

- [ ] YAML-Editor ersetzen
- [ ] Webbasierte Konfiguration
- [ ] Konfigurationsprüfung
- [ ] Backup & Restore

### Geräte

- [ ] Kameraverwaltung
- [ ] Mehrere Kameras
- [ ] RTSP
- [ ] USB-Kameras
- [ ] CSI-Kameras

### Monitoring

- [ ] CPU-Auslastung
- [ ] RAM-Auslastung
- [ ] Temperatur
- [ ] Netzwerk
- [ ] Speicherplatz

---

# Version 0.7.x

## Ziel

Erweiterbarkeit durch Plugins.

### Plugin-System

- [ ] Overlay-Plugins
- [ ] Datenquellen
- [ ] Ereignisse
- [ ] Webhooks
- [ ] Benachrichtigungen

### BOS-Erweiterungen

- [ ] Hydranten
- [ ] Sirenen
- [ ] Pegelstände
- [ ] Wetterdaten
- [ ] Einsatzmittel

---

# Langfristige Ziele

## Stabilität

- Reproduzierbare Installation
- Automatisierte Tests
- Continuous Integration
- Dokumentation

## Plattformen

- [x] Raspberry Pi
- [x] Debian-Serverprofil
- Ubuntu

## Serverbetrieb

- [x] Optionales Caddy-/HTTPS-Setup mit Let's Encrypt
- [x] Öffentliche WebRTC-/ICE-Konfiguration
- [x] Optionale Host-Firewall-Regeln mit SSH-Schutz
- [x] RTMP-Publisher in beiden Profilen mit pfadgebundenen Tokens absichern
- [ ] RTMP-Transport über VPN oder RTMPS verschlüsseln

## Bedienung

- Vollständige Bedienung über die Weboberfläche
- Mobile Optimierung
- Touch-Bedienung

## Architektur

- Klare Modulstruktur
- Erweiterbares Overlay-System
- Plugin-Schnittstellen
- Saubere Trennung zwischen Anwendung und Laufzeitdaten

---

# Projektvision

Open BOS Stream soll eine leichtgewichtige, einfach installierbare und modular erweiterbare Streaming- und Kartenplattform für Behörden und Organisationen mit Sicherheitsaufgaben (BOS) werden.

Der Fokus liegt auf:

- einfacher Installation
- robuster Betrieb auf Raspberry Pi
- modularer Architektur
- schneller Bedienung
- einfacher Erweiterbarkeit
- langfristiger Wartbarkeit

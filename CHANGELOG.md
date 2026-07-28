# Changelog

Alle wichtigen Änderungen an Open BOS Stream werden in dieser Datei dokumentiert.

Dieses Projekt orientiert sich an den Empfehlungen von
"Keep a Changelog" und verwendet Semantic Versioning für Releases.

---

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

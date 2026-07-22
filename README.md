# Open BOS Stream

> Moderne Open-Source-Streaminglösung für Behörden und Organisationen
> mit Sicherheitsaufgaben (BOS).

Open BOS Stream ist eine webbasierte Streamingplattform für den
Einsatzbetrieb. Sie ermöglicht Live-Streaming, Aufzeichnungen,
Snapshots, Medienverwaltung und Systemüberwachung auf kompakter
Hardware wie dem Raspberry Pi.

---

## Highlights

- 🎥 Live-Streaming
- ⏺ Videoaufzeichnung
- 📸 Snapshot-Funktion
- 📁 Medienbibliothek
- 📊 Dashboard mit Systemstatus
- 📱 Responsive Weboberfläche
- ⚙️ Einfache Konfiguration
- 🍓 Optimiert für Raspberry Pi
- 🔓 100 % Open Source

---

## Screenshots

> Screenshots folgen mit Version 0.4.

---

## Funktionen

### Streaming

- Livebild
- Stream starten und stoppen
- Video-Overlay
- Vollbildmodus

### Aufnahme

- Aufnahme starten und stoppen
- Laufzeitanzeige
- Aufnahmebibliothek

### Snapshots

- Snapshot erstellen
- Vorschau
- Snapshotbibliothek

### Dashboard

- CPU-Auslastung
- RAM-Auslastung
- Temperatur
- Streamstatus
- Ereignisprotokoll

### System

- FFmpeg-Status
- MediaMTX-Status
- Capture-Status

---

## Projektstruktur

```
src/open_bos_stream

├── api/
├── core/
├── dashboard/
├── mediamtx/
├── recording/
├── snapshot/
├── static/
├── stream/
├── system/
└── templates/
```

---

## Installation

```bash
git clone https://github.com/<user>/open-bos-stream.git

cd open-bos-stream

python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt
```

---

## Starten

```bash
python -m open_bos_stream.main
```

Danach ist das Dashboard erreichbar unter

```
http://localhost:8000
```

---

## Roadmap

Siehe:

```
ROADMAP.md
```

---

## Changelog

Siehe:

```
CHANGELOG.md
```

---

## Lizenz

Dieses Projekt steht unter der MIT-Lizenz.

---

## Mitwirken

Pull Requests, Fehlerberichte und Verbesserungsvorschläge sind jederzeit willkommen.

---

## Projektstatus

**Aktuelle Version**

```
v0.3.6-alpha
```

Die Software befindet sich derzeit in aktiver Entwicklung.

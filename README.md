# Open BOS Stream

Open BOS Stream ist eine webbasierte Streaming- und Kartenplattform für BOS-Anwendungen (Behörden und Organisationen mit Sicherheitsaufgaben). Sie kombiniert Live-Video, Kartenansicht und einsatzrelevante Overlays in einer leichtgewichtigen Anwendung für Raspberry Pi und Linux.

---

## Features

- Live-Streaming über FastAPI
- Kartenansicht mit Leaflet
- Dynamisches Overlay-System
- Mobile Fullscreen-Unterstützung
- Wasserentnahmestellen als Karten-Overlay
- Produktionsbetrieb über systemd
- Automatischer Installer
- Update-Mechanismus
- Automatische Installationsprüfung

---

## Voraussetzungen

- Raspberry Pi OS (Bookworm empfohlen)
- Python 3.13 oder neuer
- Git
- Internetzugang während der Installation

Die benötigten Systempakete werden automatisch installiert.

---

# Installation

Repository klonen:

```bash
git clone <repository-url>
cd open-bos-stream
```

Installer starten:

```bash
./scripts/install.sh
```

Der Installer übernimmt automatisch:

- Installation der Systemabhängigkeiten
- Deployment nach `/opt/open-bos-stream`
- Einrichtung der Produktionsumgebung
- Erstellung der Python-Virtualenv
- Installation des systemd-Dienstes
- Funktionsprüfung

---

# Update

Ein bestehendes System wird aktualisiert mit:

```bash
./scripts/update.sh
```

Dabei bleiben erhalten:

- `config/`
- `mapdata/`
- `recordings/`
- `snapshots/`

---

# Projektstruktur

```
config/             Konfiguration
mapdata/            Kartenmaterial
recordings/         Aufzeichnungen
scripts/            Installations- und Wartungsskripte
src/                Anwendung
snapshots/          Screenshots
```

Nach der Installation befindet sich die produktive Installation unter:

```
/opt/open-bos-stream
```

---

# Wichtige Installationsskripte

| Skript | Beschreibung |
|---------|--------------|
| `install.sh` | Vollständige Neuinstallation |
| `update.sh` | Aktualisierung einer bestehenden Installation |
| `verify-installation.sh` | Installationsprüfung |
| `install-service.sh` | Installation des systemd-Dienstes |

---

# Systemdienst

Status prüfen:

```bash
systemctl status open-bos-stream.service
```

Dienst neu starten:

```bash
sudo systemctl restart open-bos-stream.service
```

Logs anzeigen:

```bash
journalctl -u open-bos-stream.service -f
```

---

# Deployment-Information

Die installierte Version wird gespeichert in:

```
/opt/open-bos-stream/.deployment
```

Beispiel:

```
Version=0.4.10
Commit=abc1234
Installed=2026-07-22 18:42:11
```

---

# Entwicklung

Lokale Python-Umgebung erstellen:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Entwicklungsserver starten:

```bash
uvicorn open_bos_stream.main:app --reload
```

---

# Lizenz

Dieses Projekt steht unter der MIT-Lizenz.
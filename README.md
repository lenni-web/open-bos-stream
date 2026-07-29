# Open BOS Stream

Open BOS Stream ist eine webbasierte Streaming- und Kartenplattform für BOS-Anwendungen (Behörden und Organisationen mit Sicherheitsaufgaben). Sie kombiniert Live-Video, Kartenansicht und einsatzrelevante Overlays in einer leichtgewichtigen Anwendung für Raspberry Pi und Linux.

---

## Features

- Live-Streaming über FastAPI
- Kartenansicht mit Leaflet
- Dynamisches Overlay-System
- Mobile Fullscreen-Unterstützung
- Lokales Wayland/labwc-Display mit Chromium
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

## Lokales Display

Auf Raspberry Pi OS wird eine laufende labwc/Wayland-Desktopsitzung
benötigt. Das Display kann in den Einstellungen manuell in drei Modi
gestartet werden:

- `kiosk`: Dashboard ohne Chromium-Browserrahmen
- `normal`: normales Chromium-Fenster mit Bedienoberfläche
- `stream`: reduzierte Vollbildanzeige des Live-Streams

Der Dienst wird bewusst nicht beim Boot aktiviert. Nach einem manuellen
Start startet systemd Chromium bei einem Absturz erneut.

Status und Logs:

```bash
systemctl status open-bos-display.service
journalctl -u open-bos-display.service -f
```

Bei aktivierter Option verhindert der Dienst für seine Laufzeit
Idle- und Sleep-Energiesparzustände. Beim Stoppen wird dieses Inhibit
automatisch aufgehoben.

## Webzugriff über Port 80

Die Oberfläche bleibt immer unter `http://<geraet>:8000` erreichbar.
In den Einstellungen kann zusätzlich der HTTP-Standardport aktiviert
werden, sodass `http://<geraet>` ohne Portangabe genügt.

Ein eigener systemd-Socket leitet Port 80 intern an Port 8000 weiter.
Ist Port 80 bereits belegt, bleibt die Anwendung auf Port 8000
verfügbar und zeigt den Konflikt in den Einstellungen und auf der
Systemseite an.

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

## Passthrough

Bereits kodierte Netzwerkstreams können ohne zusätzlichen FFmpeg-Relay
direkt über MediaMTX wiedergegeben werden:

```yaml
input:
  type: rtmp
  mode: copy
  url: rtmp://127.0.0.1:1935/live/drohne

encoder:
  codec: copy

stream:
  name: live/drohne
  rtsp_url: rtsp://127.0.0.1:8554/live/drohne
  passthrough: true
```

Im Passthrough-Modus wird der Stream vom externen Publisher gesteuert.
Open BOS Stream startet dafür keinen internen FFmpeg-Streamer. Overlays,
lokales Audio und Video-Konvertierung benötigen weiterhin den normalen
Transcoding-Modus.

---

# Lizenz

Dieses Projekt steht unter der MIT-Lizenz.

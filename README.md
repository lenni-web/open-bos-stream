# Open BOS Stream

Open BOS Stream ist eine webbasierte Streaming- und Kartenplattform für BOS-Anwendungen (Behörden und Organisationen mit Sicherheitsaufgaben). Sie kombiniert Live-Video, Kartenansicht und einsatzrelevante Overlays in einer leichtgewichtigen Anwendung für Raspberry Pi und Debian-Server.

---

## Features

- Bis zu acht gleichwertige Live-Quellen mit RTMP, RTSP, SRT, UDP, HTTP,
  HLS oder lokaler Capture Card
- WebRTC-Wiedergabe mit optionalem Stream Copy, Zeitstempel-Reparatur oder
  Transcoding je Quelle
- Individuelle RTMP-Empfangspfade mit Publisher-Token
- Rollenbasierter Zugriff für Viewer, Admins und Superadmins
- Offline-Kartenansicht mit MapLibre und MBTiles
- Raspberry-Pi-Profil mit optionalem Wayland/labwc-Display
- Debian-Serverprofil mit optionalem Caddy/HTTPS, WebRTC und UFW
- Produktionsbetrieb über systemd sowie automatische Installationsprüfung
- Wiederholbarer Installer und Update-Mechanismus

---

## Voraussetzungen

- Raspberry Pi OS oder Debian
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

Der Installer fragt bei einer interaktiven Neuinstallation nach dem Profil:

- `local`: Raspberry Pi bzw. lokaler Rechner mit optionaler Capture Card und
  lokalem Wayland-Display
- `server`: Debian-Server mit Netzwerkquellen, ohne Chromium, labwc, seatd
  und Display-Dienst

Für eine nicht-interaktive Installation kann das Profil direkt angegeben
werden:

```bash
./scripts/install.sh --profile server
```

Die Auswahl wird in `/etc/open-bos-stream/profile` gespeichert. Ein Update
verwendet automatisch das vorhandene Profil. Ein bewusster Profilwechsel ist
mit `./scripts/update.sh --profile local|server` möglich.

MediaMTX wird in beiden Profilen als Systemkomponente unter
`/usr/local/bin/mediamtx` verwaltet. Ist dort noch keine Binärdatei vorhanden,
übernimmt der Installer zunächst eine vorhandene Altinstallation aus dem
`PATH` oder aus `/home/<service-user>/mediamtx`. Fehlt MediaMTX vollständig,
lädt er die zum System passende offizielle Version für `amd64`, `arm64`,
`armv7` oder `armv6`, prüft deren SHA256-Summe und installiert sie.
Der frühere Standardpfad `/home/streampi/mediamtx` wird dabei ausdrücklich
auch dann erkannt, wenn `install-service.sh` direkt aufgerufen wird.

Bei einer interaktiven Erstinstallation wird der Download bestätigt. Für
automatisierte Installationen stehen folgende Optionen zur Verfügung:

```bash
# Fehlende Installation automatisch ergänzen (Standard)
./scripts/install.sh --profile local

# Die im Projekt festgelegte Version bewusst neu installieren
./scripts/install.sh --profile server --install-mediamtx

# Eine bestimmte kompatible Version installieren
./scripts/install.sh --install-mediamtx --mediamtx-version 1.19.3

# Bereits heruntergeladenes offizielles Archiv verwenden
./scripts/install.sh \
  --mediamtx-version 1.19.3 \
  --mediamtx-archive /pfad/mediamtx_v1.19.3_linux_arm64.tar.gz

# Download deaktivieren und eine vorhandene Installation verlangen
./scripts/install.sh --no-install-mediamtx
```

Liegt neben einem lokalen Archiv eine Datei mit der Endung `.sha256`, wird
diese Prüfsumme verwendet. Andernfalls lädt der Installer die offizielle
Prüfsummendatei des gewählten Releases. Normale Updates behalten eine bereits
installierte MediaMTX-Version bei; ein Versionswechsel erfolgt nur mit
`--install-mediamtx`.

Bezugsquelle und Release-Artefakte:
[offizielle MediaMTX-Releases](https://github.com/bluenviron/mediamtx/releases).

Der Installer übernimmt automatisch:

- Installation der Systemabhängigkeiten
- Installation oder Migration von MediaMTX
- Deployment nach `/opt/open-bos-stream`
- Einrichtung der Produktionsumgebung
- Erstellung der Python-Virtualenv
- Installation des systemd-Dienstes
- Funktionsprüfung

## Installation als root und Dienstbenutzer

Der Installer kann sowohl als normaler Benutzer mit `sudo` als auch direkt
als `root` ausgeführt werden. Die Anwendung selbst läuft unabhängig davon
immer unter einem unprivilegierten Dienstkonto. Standardmäßig verwendet Open
BOS Stream weiterhin `streampi:video`, damit bestehende Raspberry-Pi-Systeme
kompatibel bleiben.

Fehlen Benutzer oder Gruppe auf einem frischen Debian-System, legt der
Installer sie automatisch an. Der Benutzer erhält ein Home-Verzeichnis und
eine gesperrte Passwortanmeldung; er wird nicht in die Gruppe `sudo`
aufgenommen. Die gewählte Identität wird dauerhaft in
`/etc/open-bos-stream/install.env` gespeichert und bei Updates wiederverwendet.

Für eine abweichende Dienstidentität:

```bash
./scripts/install.sh \
  --profile server \
  --service-user openbos \
  --service-group openbos
```

Auch ein späterer bewusster Wechsel ist möglich:

```bash
./scripts/update.sh \
  --service-user openbos \
  --service-group openbos
```

Die systemd-Units, Laufzeitverzeichnisse und notwendigen sudoers-Regeln werden
dabei neu erzeugt. Bei einem Root-Aufruf weist der Installer ausdrücklich
darauf hin, dass die Dienste trotzdem unprivilegiert gestartet werden.

Für Git bleibt der Eigentümer des geklonten Repositorys maßgeblich. Gehört
das Repository root, führt auch das Update den Git-Abruf als root aus. Bei
privaten Repositories müssen deshalb die passenden Zugangsdaten für diesen
Repository-Eigentümer vorhanden sein.

Die Installation wurde sowohl als lokales Raspberry-Pi-Profil als auch als
Serverprofil auf einem frischen Debian-System vorgesehen. Abgebrochene
Installationen können nach Behebung der Ursache erneut mit denselben Optionen
gestartet werden; vorhandene Laufzeitdaten und Konfigurationen bleiben dabei
erhalten.

## Öffentliches Serverprofil: HTTPS, WebRTC und Firewall

Bei einer interaktiven Serverinstallation fragt der Installer zusätzlich:

- öffentliche Domain
- HTTPS-Einrichtung mit Caddy und Let's Encrypt
- öffentliche WebRTC-Bereitstellung
- optionale Verwaltung der Host-Firewall mit UFW

Eine vollständige nicht-interaktive Installation ist beispielsweise:

```bash
./scripts/install.sh \
  --profile server \
  --domain stream.example.de \
  --https \
  --webrtc public \
  --firewall configure
```

Die Serverparameter werden in `/etc/open-bos-stream/server.env` gespeichert.
Normale Updates verwenden diese Werte ohne erneute Rückfragen. Sie können
bewusst über das Update-Skript geändert werden:

```bash
./scripts/update.sh \
  --domain stream.example.de \
  --https \
  --webrtc public \
  --firewall configure
```

Oder unabhängig von einem Update:

```bash
./scripts/configure-server-access.sh --interactive
```

Verfügbare Optionen:

| Option | Wirkung |
|---|---|
| `--domain NAME` | öffentliche DNS-Domain; Hostname oder `https://`-Adresse |
| `--https` | Caddy installieren und HTTPS aktivieren |
| `--no-https` | verwalteten Caddy-Zugriff deaktivieren |
| `--webrtc public` | Domain als öffentlichen WebRTC-/ICE-Host eintragen |
| `--webrtc local` | keine öffentliche WebRTC-Domain konfigurieren |
| `--firewall configure` | UFW-Regeln verwalten und aktivieren |
| `--firewall off` | vorhandene Firewall nicht verändern |

Vor der HTTPS-Aktivierung muss der A- beziehungsweise AAAA-Eintrag der Domain
auf den Server zeigen. Caddy fordert das Zertifikat direkt bei Let's Encrypt
an, erneuert es automatisch und leitet HTTP auf HTTPS um. Certbot wird nicht
benötigt.

Unter HTTPS werden alle Browserzugriffe über dieselbe Domain geführt:

```text
https://stream.example.de/              Open BOS Stream
https://stream.example.de/whep/...      WebRTC/WHEP
https://stream.example.de/hls/...       HLS
```

Uvicorn, HLS, WHEP, RTSP und die MediaMTX-API lauschen dabei ausschließlich
lokal. Der WebRTC-Medienstrom verwendet weiterhin UDP 8189. MediaMTX erhält
die öffentliche Domain automatisch als `webrtcAdditionalHosts`.

Wenn HTTPS deaktiviert bleibt, verwendet die Anwendung weiterhin die direkten
Ports 8000, 8888 und 8889.

### Firewall-Regeln

Bei `--firewall configure` erkennt der Installer zunächst den SSH-Port und
lässt ihn geöffnet. Anschließend verwaltet er folgende Open-BOS-Regeln:

| Port | Protokoll | Funktion |
|---|---|---|
| SSH-Port | TCP | Administration |
| 80 | TCP | HTTP und ACME-Prüfung |
| 443 | TCP | HTTPS, WHEP und HLS |
| 1935 | TCP | RTMP-Publisher |
| 8189 | UDP | WebRTC-Medien |

Ohne HTTPS werden statt 80/443 die direkten Ports 8000, 8888 und 8889
freigegeben. Eine zusätzliche Firewall des vServer-Anbieters kann der
Installer nicht verändern und muss dort entsprechend konfiguriert werden.

### RTMP-Publisher-Token

In beiden Installationsprofilen erhält jede RTMP-Quelle automatisch einen
eigenen, zufälligen Publisher-Token mit genau 12 Zeichen. Die vollständige
Empfangsadresse ist in den Einstellungen zunächst verdeckt und kann bewusst
eingeblendet werden:

```text
rtmp://server.example:1935/quelle-1?token=GEHEIMNIS
```

MediaMTX fragt die Anwendung bei jeder externen Veröffentlichung ab. Dabei
müssen Quellen-ID und Token zusammenpassen; ein Token einer anderen Quelle
genügt nicht. Bestehende RTMP-Quellen erhalten beim ersten Laden nach dem
Update automatisch einen persistenten Token. Ältere, längere Tokens werden
einmalig auf die ersten 12 Zeichen gekürzt.

Der Token kann in der Quellenkonfiguration nach dem Einblenden selbst
festgelegt werden. Er muss aus genau 12 Buchstaben, Zahlen, Bindestrichen oder
Unterstrichen bestehen. Die zusammengesetzte Publisher-URL bleibt
schreibgeschützt und aktualisiert sich automatisch, sobald ID oder Token
geändert werden.

Der Token verhindert unbefugtes Publizieren, verschlüsselt den Transport aber
nicht. Port 1935 sollte deshalb möglichst über die Anbieter-Firewall auf
bekannte Absender-IP-Adressen beschränkt werden. VPN oder RTMPS sind als
spätere Härtung vorgesehen.

## Offline-Karte Landkreis Stade

Die Kartendaten sind wegen ihrer Größe nicht Bestandteil des Repositorys.
Für den Landkreis Stade steht eine vorbereitete MBTiles-Datei bereit:

[Karte Landkreis Stade herunterladen](https://nextcloud.lenni-web.de/index.php/s/YXpLgCPG5Twm8MP)

Die heruntergeladene Datei muss auf einer Standardinstallation als
`stade.mbtiles` in folgendem Pfad liegen:

```text
/opt/open-bos-stream/mapdata/stade.mbtiles
```

Beispiel zum Installieren einer bereits auf den Raspberry Pi übertragenen
Datei:

```bash
sudo install \
  -o streampi \
  -g video \
  -m 0644 \
  /pfad/zur/heruntergeladenen-datei.mbtiles \
  /opt/open-bos-stream/mapdata/stade.mbtiles
```

Wenn ein abweichender Kartenpfad konfiguriert wurde, zeigt die Kartenansicht
bei fehlender Datei den tatsächlich verwendeten Zielpfad an.

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
| `configure-server-access.sh` | Caddy, WebRTC und optionale UFW-Regeln |

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

Der Display-Dienst startet bei Bedarf eine eigene minimale
labwc/Wayland-Sitzung und öffnet darin Chromium. Dadurch funktioniert die
Anzeige auch auf Raspberry Pi OS, wenn nach dem Boot zunächst nur die
Shell-Konsole sichtbar ist. labwc, seatd und die D-Bus-Komponenten werden
vom Installationsskript eingerichtet. Das Display kann in den Einstellungen
manuell in drei Modi gestartet werden:

- `kiosk`: Dashboard ohne Chromium-Browserrahmen
- `normal`: normales Chromium-Fenster mit Bedienoberfläche
- `stream`: reduzierte Vollbildanzeige des Live-Streams

Der Dienst wird bewusst nicht beim Boot aktiviert. Nach einem manuellen
Start startet systemd die Display-Sitzung bei einem Absturz erneut.

Status und Logs:

```bash
systemctl status open-bos-display.service
journalctl -u open-bos-display.service -f
```

In der eigenständigen minimalen labwc-Sitzung wird kein Bildschirmschoner
oder Desktop-Power-Manager gestartet. Bei aktivierter Option bleibt die
Anzeige daher ohne zusätzliche, privilegierte Inhibit-Sperre aktiv.

## Mehrere gleichwertige Quellen

In den Einstellungen können bis zu acht Quellen angelegt werden. Unterstützt
werden alle vorhandenen Eingangsadapter: Capture Card, RTMP, RTSP, SRT, UDP,
HTTP und HLS. Jede Quelle besitzt einen eigenen Namen, eine strikt validierte
ID sowie ein Verarbeitungsprofil:

- `Direkt / Stream Copy`: Video ohne Neukodierung übernehmen
- `Copy mit Zeitstempel-Korrektur`: Originalvideo mit reparierten Zeitstempeln
- `Transcodieren`: den pro Quelle gewählten Encoder verwenden

Bei `Transcodieren` erscheinen Encoder, Bitrate, Pixelformat, GOP, Preset und
Tune direkt innerhalb der betroffenen Quelle. Es gibt keine missverständliche
globale Transcoding-Karte mehr; Quellen können unterschiedliche Einstellungen
verwenden.

Die Quellen lassen sich mit den Pfeilschaltflächen umsortieren. Diese
Reihenfolge wird gespeichert und ebenso im Livebildraster verwendet.
Das optionale Feld „Drohnen-Typ“ hält je Quelle das eingesetzte Modell fest,
ohne die technische Verarbeitung oder Empfangsadresse zu beeinflussen.

Bei RTMP wird der Empfangspfad automatisch aus der ID erzeugt und kann nicht
separat verändert werden. In beiden Installationsprofilen hängt die
Oberfläche den individuellen, standardmäßig verdeckten Publisher-Token an:

```text
rtmp://<Server-IP>:1935/quelle-1?token=<TOKEN-DER-QUELLE>
rtmp://<Server-IP>:1935/quelle-2?token=<TOKEN-DER-QUELLE>
```

IDs dürfen ausschließlich Kleinbuchstaben, Zahlen, Bindestriche und
Unterstriche enthalten. MediaMTX prüft alle Pfade gemeinsam; das Dashboard
öffnet eine WebRTC-Kachel erst, wenn der jeweilige Stream verfügbar ist.

RTSP-Netzwerkkameras können direkt als Quelle eingetragen werden, zum Beispiel:

```text
rtsp://admin:PASSWORT@192.168.1.50:554/Preview_01_main
```

Zugangsdaten werden in der Oberfläche maskiert und in Streamer-Protokollen
redigiert. Verwaltete Quellen werden durch einen systemd-Dienst überwacht.

## Benutzer und Rollen

Beim ersten Aufruf nach Installation oder Update fordert Open BOS Stream dazu
auf, ein lokales Superadmin-Konto anzulegen. Benutzer und Passwort-Hashes
werden ausschließlich in `config/users.yaml` gespeichert; die Datei und der
lokale Sitzungsschlüssel werden nicht in Git übernommen.

- `viewer`: Übersicht, Streams, Karte und Systemstatus ansehen
- `admin`: zusätzlich Quellen anlegen, bearbeiten, sortieren und entfernen
- `superadmin`: zusätzlich Medien, Benutzer, Streaming-Ausgänge, lokales
  Display und Webzugriff verwalten

Die Rechte werden sowohl in der Oberfläche als auch an den API-Endpunkten
geprüft. Ein Admin kann geschützte Superadmin-Felder daher nicht über einen
direkten API-Aufruf verändern. Quellenänderungen von Admins werden über einen
eigenen Endpunkt gespeichert, der die übrige Systemkonfiguration unverändert
vom Server übernimmt.

Superadmins können bestehende Konten in den Einstellungen aufklappen, deren
Rolle ändern oder ein neues Passwort vergeben. Mindestens ein Superadmin muss
immer erhalten bleiben.

Der lokale Kiosk erhält ausschließlich eine auf Loopback begrenzte
Viewer-Ansicht. Im normalen Chromium-Modus ist eine reguläre Anmeldung nötig,
wenn Einstellungen bedient werden sollen.
Eine vorübergehend nicht erreichbare Quelle wird unabhängig mit begrenztem
Backoff neu verbunden und unterbricht die übrigen Quellen nicht.

## Webzugriff im lokalen Profil

Die Oberfläche bleibt immer unter `http://<geraet>:8000` erreichbar.
In den Einstellungen kann zusätzlich der HTTP-Standardport aktiviert
werden, sodass `http://<geraet>` ohne Portangabe genügt.

Ein eigener systemd-Socket leitet Port 80 intern an Port 8000 weiter.
Ist Port 80 bereits belegt, bleibt die Anwendung auf Port 8000
verfügbar und zeigt den Konflikt in den Einstellungen und auf der
Systemseite an.

Diese Umschaltung gilt nur für das lokale Profil. Im Server-Profil übernimmt
Caddy die Ports 80 und 443. Bei aktiviertem HTTPS ist Port 8000 nur noch über
Loopback erreichbar.

## RTMP Copy mit Zeitstempel-Reparatur

Für RTMP-Quellen mit rückwärtslaufenden DTS, fehlenden Zeitstempeln
oder stark schwankenden Paketabständen steht das Quellenprofil
`RTMP Copy mit Zeitstempel-Reparatur` zur Verfügung. Das Video wird
nicht neu kodiert. FFmpeg kopiert den Originalcodec und normalisiert
den Zeitverlauf zwischen zwei getrennten MediaMTX-Pfaden. Lokale
RTMP-Eingänge werden intern über den RTSP/TCP-Spiegel gelesen, damit
MediaMTX den lokalen Leser bei stark fehlerhafter Frame-Reihenfolge
nicht schon vor der Reparatur beendet.

Beispiel:

```text
RTMP-Eingang:       rtmp://127.0.0.1:1935/live/drohne
Stabilisierte Ausgabe: rtsp://127.0.0.1:8554/drohne
```

Die Systemseite zeigt zusätzlich die gemessene Eingangsbitrate,
Paketabstände sowie lokale WebRTC-Statistiken des aktuellen Browsers.

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

# Open BOS Stream

<img src="src/open_bos_stream/static/icons/open-bos-stream.svg" alt="Open BOS Stream" width="96">

Open BOS Stream ist eine webbasierte Plattform für Drohneneinsätze von BOS (Behörden und Organisationen mit Sicherheitsaufgaben). Sie kombiniert Live-Video, Lagekarte, Flugwetter und einsatzrelevante Overlays in einer leichtgewichtigen Anwendung für Debian-Server und Raspberry Pi.

In der Oberfläche heißt die Anwendung seit Version 0.20.5 **Open BOS Drohnen**.
Repository, Python-Paket, Dienste und Pfade (`/opt/open-bos-stream`) behalten
ihren technischen Namen.

Die HTTPS-Oberfläche kann auf iOS über „Zum Home-Bildschirm“ und auf Android
über „App installieren“ beziehungsweise „Zum Startbildschirm hinzufügen“ als
eigenständige Web-App mit Open-BOS-Stream-Icon abgelegt werden.

---

## Features

- Beliebig viele gleichwertige Live-Quellen mit RTMP, RTSP, SRT, UDP, HTTP,
  HLS oder lokaler Capture Card; die Serverlast wird überwacht und bei hoher
  Auslastung ein Hinweis angezeigt
- WebRTC-Wiedergabe mit optionalem Stream Copy, Zeitstempel-Reparatur oder
  Transcoding je Quelle; Vollbild im Originalstream
- Individuelle RTMP-Empfangspfade mit Publisher-Token
- Weiterleitung einzelner Quellen an weitere Ziele per RTMP, SRT oder RTSP
- Aufnahmen und Snapshots in voller Qualität mit Mediathek,
  „Behalten“-Markierung und Speicherschutz
- Kartenansicht mit MapLibre 6: amtliche Online-Karte (basemap.de), Luftbild
  Niedersachsen (LGLN DOP20) oder Offline-Karte (MBTiles), dazu
  Wasserentnahmestellen und Drohnen-Geozonen (dipul)
- Wetter für den Flugbetrieb: DWD-Messwerte, Wind in 120 m Höhe,
  DWD-Warnungen, Kp-Index, Wetter-Ampel und Niederschlagsradar mit
  Vorhersage
- Landkreis, Samtgemeinde- und Ortsfeuerwehren mit Rollen (Zuschauer,
  Drohnenteam, Wehr-Admin), vererbten Rechten und getrennten Quellen je Wehr
- Fernpilotennachweise (A1/A3, A2, STS) mit Ablaufdatum
- Zeitlich begrenzte Gastlinks für ausgewählte Livebilder, ohne Konto
- E-Mail-Benachrichtigung bei Störungen mit Entwarnung
- Moderne Oberfläche mit Hell-/Dunkelmodus, optimiert für Smartphone,
  Tablet und Desktop
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
./scripts/install.sh --install-mediamtx --mediamtx-version 1.21.4

# Bereits heruntergeladenes offizielles Archiv verwenden
./scripts/install.sh \
  --mediamtx-version 1.21.4 \
  --mediamtx-archive /pfad/mediamtx_v1.21.4_linux_arm64.tar.gz

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

Caddy versieht öffentliche Antworten mit HSTS, MIME-Schutz, restriktiven
Frame-, Referrer- und Berechtigungsrichtlinien. HLS- und WHEP-Anfragen werden
vor der Weiterleitung gegen die Open-BOS-Sitzung geprüft. Das Sitzungscookie
trägt hinter HTTPS das Attribut `Secure`.

MediaMTX fragt bei jedem Lesezugriff die Anwendung. Erlaubt sind nur Leser
auf dem Server selbst (Caddy nach Sitzungsprüfung, interne FFmpeg-Prozesse,
lokales Display) sowie Browser mit einem kurzlebigen Medien-Token aus ihrer
Anmeldung. Streams lassen sich deshalb weder über den RTMP-Port 1935 noch
über RTSP, SRT oder die direkten HLS-/WHEP-Ports ohne Anmeldung abspielen.

Nach fünf fehlgeschlagenen Anmeldungen derselben Benutzer-/IP-Kombination
wird diese für 15 Minuten gesperrt. Zusätzlich greift eine IP-weite Grenze
gegen das Durchprobieren vieler Konten; über den lokalen Port-80-Proxy, der
alle Geräte als `127.0.0.1` erscheinen lässt, gilt nur die Sperre je Konto.
Fehlversuche und temporäre Sperren werden ohne Passwörter im
Anwendungsjournal protokolliert. Abmelden macht die Sitzung serverseitig
ungültig.

Wenn HTTPS deaktiviert bleibt, verwendet die Anwendung weiterhin die direkten
Ports 8000, 8888 und 8889. Passwörter und Bilder werden dann unverschlüsselt
übertragen; der Installer weist darauf hin.

### Firewall-Regeln

Bei `--firewall configure` erkennt der Installer zunächst den SSH-Port und
lässt ihn geöffnet. Anschließend verwaltet er folgende Open-BOS-Regeln:

| Port | Protokoll | Funktion |
|---|---|---|
| SSH-Port | TCP | Administration |
| 80 | TCP | HTTP und ACME-Prüfung |
| 443 | TCP | HTTPS, WHEP und HLS |
| 1935 | TCP | RTMP-Sender (Drohnen-Apps) |
| 8890 | UDP | SRT-Sender (geringe Latenz, z. B. Raspberry Pi) |
| 8189 | UDP und TCP | WebRTC-Medien mit TCP-Rückfallweg |

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

### SRT-Empfang mit geringer Latenz

Neben RTMP kann eine Quelle vom Typ „Sender → Server“ per **SRT** empfangen
werden. SRT läuft über UDP, gleicht Paketverluste aus und hält die
Verzögerung über einen festen Puffer klein – geeignet für Sender über
Mobilfunk, etwa einen Raspberry Pi mit HDMI-Capture-Card vor Ort. Typisch
sind 0,5 bis 1 Sekunde Ende-zu-Ende.

In der Quelle wird dazu „Empfangsprotokoll: SRT“ gewählt. Die Empfangsadresse
lautet dann:

```text
srt://server.example:8890?streamid=publish:quelle-3:token=GEHEIMNIS&latency=400000&pkt_size=1316
```

Apps mit eigenem Feld für die Stream-ID erhalten `publish:quelle-3:token=…`
und als Server `srt://server.example:8890`. Die Latenz legt der Sender fest;
300 bis 500 ms sind für Mobilfunk ein guter Wert (`latency` in Mikrosekunden
bei FFmpeg). Pfad und Token werden genauso geprüft wie bei RTMP; ein SRT-
Sender wird für eine RTMP-Quelle abgelehnt und umgekehrt. Alle Profile
(Direkt, Reparatur, Vorschau, Aufnahme, Weiterleitung) funktionieren
unverändert.

Die Host-Firewall öffnet dafür UDP 8890 (`--firewall configure`). Eine
Firewall des vServer-Anbieters muss UDP 8890 zusätzlich freigeben. Wie bei
RTMP schützt der Token vor fremden Sendern, verschlüsselt die Übertragung
aber nicht.

### Raspberry Pi vor Ort: HDMI-Bild per SRT an den Server

Ein Raspberry Pi mit HDMI-Capture-Card (lokales Profil) kann das Bild eines
Drohnen-Controllers oder einer Kamera mit geringer Verzögerung über Mobilfunk
an den Server senden. Der Pi kodiert dabei nur einmal; dasselbe Bild steht
zusätzlich vor Ort im Browser zur Verfügung.

1. **Server:** eine Quelle „Sender → Server (RTMP oder SRT)“ mit
   Empfangsprotokoll **SRT** anlegen und die SRT-Empfangsadresse kopieren.
2. **Pi, Quelle:** die Capture Card als Quelle mit dem Profil
   **„Transcodieren · geringe Latenz (Mobilfunk)“** einrichten. Encoder:
   `h264_v4l2m2m` (Hardware-Encoder des Pi 4); als Rückfall `libx264`.
   Für Mobilfunk eignen sich 1280×720 bei 25 fps und 2–3 Mbit/s.
   Das Profil setzt ein Schlüsselbild pro Sekunde, verzichtet auf B-Frames
   und minimiert alle Puffer; bei `libx264` zusätzlich `ultrafast` und
   `zerolatency`.
3. **Pi, Streaming-Ausgang:** Typ **SRT**, als Quelle die Capture Card, als
   Ziel die kopierte SRT-Adresse des Servers. Der Ausgang übernimmt das
   Video unverändert, puffert nicht zwischen und setzt – falls in der
   Adresse nicht anders angegeben – einen SRT-Puffer von 400 ms.

Erwartet werden etwa 0,5 bis 1 Sekunde vom HDMI-Eingang bis zum Browser.
Liefert die Capture-Card MJPEG, dekodiert der Pi jedes Bild vor dem Kodieren;
bei 1080p kann das die CPU des Pi 4 stark belasten, 720p ist die sichere
Wahl.

### Raspberry Pi vor Ort: RTSP vom Controller weiterleiten

Manche Controller senden nicht selbst per RTMP, sondern stellen einen
RTSP-Stream bereit, z. B. Parrot SkyController, Skydio Enterprise Controller,
Autel Smart Controller oder DJI Pilot 2. Der Server im Internet erreicht den
Controller nicht direkt. Ein Raspberry Pi vor Ort holt den Stream ab und
sendet ihn **ohne Neukodieren** per SRT an den Server.

1. **Netzwerk zum Controller:** Netzwerkkabel von der LAN-Buchse des Pi zu
   einem USB-C-Ethernet-Adapter am Controller. Das Skript richtet die
   Verbindung ein; der Weg ins Internet bleibt beim Mobilfunk:

   ```bash
   # Controller vergibt die Adresse (Parrot SkyController)
   ./scripts/pi-controller-network.sh dhcp
   # Pi vergibt die Adresse 10.42.0.x (Skydio und andere)
   ./scripts/pi-controller-network.sh share
   # Verbindung, Standardroute und vergebene Adressen prüfen
   ./scripts/pi-controller-network.sh status
   ```

   Alternativ hängen Pi und Controller im selben WLAN, etwa am
   Mobilfunk-Router.
2. **Server:** eine Quelle „Sender → Server (RTMP oder SRT)“ mit
   Empfangsprotokoll **SRT** anlegen und die SRT-Empfangsadresse kopieren.
3. **Pi, Quelle:** Typ **RTSP**, unter „Controller-Vorlage“ den Controller
   wählen. Die Vorlage setzt Transport und das Profil „Copy-Reparatur ·
   geringe Latenz“; die genaue RTSP-Adresse zeigt die Controller-App.
4. **Pi, Streaming-Ausgang:** Typ **SRT**, als Quelle die RTSP-Quelle, als
   Ziel die SRT-Adresse des Servers.

Die Vorlagen beruhen auf Herstellerangaben und sind noch nicht mit echten
Geräten geprüft. Autel und DJI können alternativ direkt per RTMP an den
Server senden; das ist meist einfacher.

## Karte: Grundkarten online und offline

Die Karte nutzt MapLibre GL JS 6. Als Grundkarte stehen im Menü
„Kartenebenen“ zur Wahl; jeder Browser merkt sich seine Auswahl:

| Grundkarte | Quelle | Abdeckung |
|---|---|---|
| Karte (basemap.de) | basemap.de Web Vektor, © basemap.de / BKG, Datenquellen © GeoBasis-DE | Deutschland, amtliche Daten, monatlich aktualisiert; in der dunklen Darstellung der Nachtstil |
| Luftbild (Niedersachsen) | Digitale Orthophotos DOP20 des LGLN, Lizenz CC BY 4.0 | Niedersachsen, 20 cm je Pixel; Beschriftungen von basemap.de darüber, außerhalb Niedersachsens die Karte |
| Offline-Karte | eigene MBTiles-Datei (siehe unten) | je nach Datei, ohne Internet |

Alle Online-Abrufe laufen über den Server: Vektorkacheln werden komprimiert,
Luftbilder in WebP umgerechnet (rund 20 KB je Kachel) und einen Tag
zwischengespeichert. Browser verbinden sich nicht mit den Kartendiensten.
Ist der Online-Dienst nicht erreichbar, zeigt die Karte die Offline-Karte
mit einem Hinweis, sofern eine installiert ist. Wasserentnahmestellen,
Geozonen und Regenradar bleiben beim Wechsel der Grundkarte erhalten. Die
Radarseite nutzt ebenfalls basemap.de.

Ohne Internetzugang (z. B. auf einem Pi vor Ort) werden die Online-Karten in
`config/stream.yaml` abgeschaltet:

```yaml
map:
  online: false        # nur Offline-Karte
  base_map: offline    # Voreinstellung: online, aerial oder offline
```

## Offline-Karte Landkreis Stade

Mit den Online-Karten ist eine Offline-Karte auf dem Server optional; für
den Pi vor Ort und als Rückfall bleibt sie sinnvoll. Die Kartendaten sind
wegen ihrer Größe nicht Bestandteil des Repositorys. Für den Landkreis Stade
steht eine vorbereitete MBTiles-Datei bereit:

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

### Drohnen-Geozonen (dipul)

Die Karte kann zusätzlich die Geozonen für Drohnen der Digitalen Plattform
Unbemannte Luftfahrt (dipul) einblenden. Die 33 aktuellen dipul-Ebenen sind
im Menü „Kartenebenen“ zu Gruppen zusammengefasst:

| Gruppe | Enthaltene Ebenen | Standard |
|---|---|---|
| Luftraum | Kontrollzonen, Flughäfen, Flugplätze, Flugbeschränkungsgebiete | an |
| Temporäre Einschränkungen | Temporäre Betriebseinschränkungen (z. B. NOTAM) | an |
| Schutzgebiete | Naturschutz-, FFH- und Vogelschutzgebiete, Nationalparks | an |
| Infrastruktur | Industrieanlagen, Kraftwerke, Umspannwerke, Stromleitungen, Windkraftanlagen | an |
| Verkehrswege | Autobahnen, Bundesstraßen, Bahnanlagen, Binnen-/Seewasserstraßen, Schifffahrtsanlagen | an |
| Einrichtungen | Krankenhäuser, Polizei, Behörden, JVA, Militär, Vertretungen, BSL-4-Labore u. a. | an |
| Sonstiges | Wohngrundstücke, Freibäder, Modellflugplätze, Hängegleiter | an |

Ein Klick auf die Karte zeigt die Geozonen der eingeblendeten Gruppen an
dieser Stelle mit Name, Art, Höhenbegrenzung und Rechtsgrundlage.

Die Kartenbilder ruft der Open-BOS-Server vom öffentlichen dipul-WMS
(`https://uas-betrieb.de/geoservices/dipul/wms`) ab und speichert sie eine
Stunde zwischen. Browser bauen dadurch keine Verbindung zu dipul auf, und
wiederholte Aufrufe belasten den Dienst nicht. Der Server benötigt dafür
ausgehenden HTTPS-Zugriff. Ist dipul nicht erreichbar, bleibt die
Offline-Karte nutzbar und unter der Karte erscheint ein Hinweis.

Die Daten stehen unter der Lizenz CC BY-ND 4.0 und werden unverändert
angezeigt; die Quellenangabe steht unter der Karte und in der Kartenecke.
Die Ebene dient nur der Orientierung, ist nicht rechtsverbindlich und
ersetzt nicht die Prüfung im offiziellen dipul-Map-Tool vor einem Flug.

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

### Wetter und Niederschlagsradar

Die Übersicht zeigt für alle angemeldeten Nutzer eine Wetterkarte für den
Flugbetrieb, die Karte zusätzlich das Wetter der Kartenmitte und auf Wunsch
das Niederschlagsradar des DWD.

Der Menüpunkt **Wetter** bündelt alles auf einer Seite: dieselben Angaben wie
die Übersicht mit einer Vorhersage über 24 Stunden und eine eigene
Radarkarte mit **Zeitleiste**. Ein Schieberegler wählt den Zeitpunkt von zwei
Stunden zurück bis 90 Minuten voraus (alle 10 Minuten), „Abspielen“ zeigt die
Bewegung der Niederschlagsgebiete als Animation. Bilder bis „Jetzt“ sind
Messungen, danach die Vorhersage des DWD (Radar-Nowcast). Alle Zeitpunkte
laden im Hintergrund – zuerst „Jetzt“, dann von dort nach außen –, damit die
Animation ohne Nachladen läuft. Vergangene Bilder speichert der Server eine
Stunde zwischen, aktuelle und vorhergesagte vier Minuten.

| Angabe | Quelle | Aktualisierung |
|---|---|---|
| Messwerte der nächsten DWD-Station (Wind, Böen, Temperatur, Niederschlag, Sicht) | Bright Sky (Daten: DWD) | 10 Minuten |
| Vorhersage der nächsten 24 Stunden, Wind in 80 und 120 m Höhe | Open-Meteo, Modell DWD ICON | 30 Minuten |
| Amtliche Wetterwarnungen für die Gemeinde | Bright Sky (Daten: DWD) | 10 Minuten |
| Kp-Index, angezeigt als „Satellitennavigation“: ruhig, unruhig (ab 4), Sturm (ab 5) | NOAA SWPC | 60 Minuten |
| Taupunkt, Taupunktdifferenz, geschätzte Wolkenuntergrenze (125 m je °C Differenz) | aus Messwerten bzw. Vorhersage berechnet | mit den Messwerten |
| Sonnenauf- und -untergang, bürgerliche Dämmerung | auf dem Server berechnet | laufend |
| Niederschlagsradar: 2 Stunden Rückblick, Vorhersage bis +90 Minuten | DWD-GeoServer (Produkt RV) | 5 Minuten |

Die **Wetter-Ampel** vergleicht die Werte mit einstellbaren Grenzwerten
(Einstellungen → Wetter): Dauerwind am Boden und in 120 m, Böen, Temperatur,
Niederschlag und Sicht. Gelb bedeutet „nahe am Grenzwert“ (ab 75 %), leichter
Niederschlag, Kp ab 4, eine markante DWD-Warnung, eine kritische Stunde in
der Vorhersage, eine Taupunktdifferenz bis 2 °C (Nebel, beschlagene Optik),
eine geschätzte Wolkenuntergrenze unter 200 m, Vereisungsgefahr (−10 bis
+3 °C bei feuchter Luft oder Niederschlag) oder Dunkelheit nach Ende der
bürgerlichen Dämmerung; Rot bedeutet einen überschrittenen Grenzwert, Kp ab 5 oder eine
Unwetterwarnung. Die Voreinstellungen (10 m/s Wind, 12 m/s Böen, −10 bis
40 °C) entsprechen den empfindlichsten Geräten wie Mavic 3T und Matrice 4T;
eine Flotte mit Matrice 30/350 kann höhere Werte eintragen. Die Ampel ist eine
Orientierungshilfe – maßgeblich bleiben die Herstellerangaben und die
Entscheidung der Fernpilotin oder des Fernpiloten.

Ohne eigenen Standort gilt die Kartenmitte. Alle Abrufe laufen über den
Server und werden zwischengespeichert; Browser verbinden sich nicht mit den
Wetterdiensten. Der Server braucht dafür ausgehenden HTTPS-Zugriff. Fällt
eine Quelle aus, zeigen die übrigen weiter Daten. Ohne Internetzugang (z. B.
auf einem Pi vor Ort ohne Mobilfunk) lässt sich das Wettermodul in den
Einstellungen ausschalten.

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

In den Einstellungen lassen sich beliebig viele Quellen anlegen; eine feste
Obergrenze gibt es nicht. Stattdessen bewertet die Anwendung laufend CPU,
Arbeitsspeicher und Systemlast (Mittelwert über 30 Sekunden) und zeigt bei
hoher Auslastung auf allen Seiten einen Hinweis; hält eine Überlastung länger
als zwei Minuten an, gibt es eine Benachrichtigung per E-Mail bzw. Push.
Unterstützt
werden alle vorhandenen Eingangsadapter: Capture Card, RTMP, RTSP, SRT, UDP,
HTTP und HLS. Jede Quelle besitzt einen eigenen Namen, eine strikt validierte
ID sowie ein Verarbeitungsprofil:

- `Direkt / Stream Copy`: Video ohne Neukodierung übernehmen
- `Copy mit Zeitstempel-Korrektur`: Originalvideo mit reparierten Zeitstempeln
- `Copy-Reparatur · geringe Latenz`: kleinere Eingangsqueue und eng begrenzter
  RTSP-Puffer für bereits weitgehend stabile Quellen
- `Mehrquellen-Vorschau · ausgewogen (max. 480p)` (nur RTMP): transkodierte
  H.264-Vorschau mit maximal 854×480 Pixeln, 12 fps und etwa 1,1 Mbit/s;
  empfohlen für bis zu vier gleichzeitig aktive Quellen
- `Mehrquellen-Vorschau · sparsam (max. 360p)` (nur RTMP): transkodierte
  H.264-Vorschau mit maximal 640×360 Pixeln, 12 fps und etwa 800 kbit/s;
  empfohlen für viele gleichzeitige Quellen oder knappere CPU-Reserven
- `Transcodieren`: den pro Quelle gewählten Encoder verwenden

Bei `Transcodieren` erscheinen Encoder, Bitrate, Pixelformat, GOP, Preset und
Tune direkt innerhalb der betroffenen Quelle. Es gibt keine missverständliche
globale Transcoding-Karte mehr; Quellen können unterschiedliche Einstellungen
verwenden.

Die Quellen lassen sich mit den Pfeilschaltflächen umsortieren. Diese
Reihenfolge wird gespeichert und ebenso im Livebildraster verwendet.
Das optionale Feld „Drohnen-Typ“ hält je Quelle das eingesetzte Modell fest,
ohne die technische Verarbeitung oder Empfangsadresse zu beeinflussen.

RTSP-Quellen können zusätzlich eine maskierte `Vorschau-URL` erhalten. Ist
sie gesetzt, nutzt die Liveübersicht diesen Stream anstelle der Haupt-URL.
Für 4K-/H.265-Kameras empfiehlt sich hier ein H.264-Substream mit 720p oder
1080p. Das reduziert Decoder- und WebRTC-Last deutlich. Beim Öffnen des
Vollbildmodus wechselt nur der gewählte Player auf einen separaten Viewerpfad
des Hauptstreams. Dieser Relay wird erst bei Bedarf gestartet, von mehreren
gleichzeitigen Vollbildnutzern gemeinsam verwendet und nach dem letzten Nutzer
mit zehn Sekunden Nachlaufzeit wieder beendet. Während des Starts und bei einem
Fehler bleibt der Substream sichtbar; beim Schließen wird ebenfalls wieder
der Substream verwendet. Eine leere Vorschau-URL verwendet weiterhin den
Hauptstream.

Liefert ein RTMP-Publisher nur einen einzelnen Stream, erzeugen die beiden
Mehrquellen-Profile daraus eine leichtere Browserausgabe. `Ausgewogen`
begrenzt das Bild auf 854×480, 12 fps und etwa 1,1 Mbit/s. Diese Variante ist
für bis zu vier gleichzeitig aktive Quellen der empfohlene Standard und bleibt
auf Tablets deutlich klarer. `Sparsam` begrenzt auf 640×360, 12 fps und etwa
800 kbit/s. Diese Variante ist für mehr parallele Quellen oder schwächere
Server vorgesehen. Beide Skalierungen erhalten das Seitenverhältnis;
720p-, 1080p-, 4K- und abweichende Formate funktionieren gleichermaßen und
kleinere Quellen werden nicht vergrößert. Audio ist in der Vorschau
deaktiviert. Das CPU-sparende `ultrafast`-Preset hält mehrere parallele
Vorschauen leichter in Echtzeit. Beim Vollbild wechselt der Browser bei beiden
Profilen auf den unveränderten RTMP-Eingang. Da die Vorschauen per Software
kodiert werden, sollte ihre CPU-Auslastung vor einem breiten Einsatz mit realen
Quellen geprüft werden.

Bestehende Konfigurationen mit dem bisherigen Mehrquellen-Profil werden nach
dem Update automatisch als `ausgewogen` interpretiert. Wer die geringere Last
der 360p-Variante behalten möchte, wählt anschließend ausdrücklich `sparsam`.

Snapshots und Aufnahmen verwenden immer den Originalstream in voller Qualität,
auch wenn die Liveübersicht eine reduzierte Vorschau zeigt. Bei den
RTMP-Vorschauprofilen ist das der unveränderte Publisherpfad, bei RTSP mit
Vorschau-URL der Kamera-Hauptstream. Dieser wird über denselben
bedarfsgesteuerten Relay wie die Vollbildanzeige bereitgestellt und während
einer Aufnahme offen gehalten. Steht der Hauptstream innerhalb von acht
Sekunden nicht bereit, wird ersatzweise die Vorschau verwendet; der
Medienbalken weist dann auf die Vorschauqualität hin.

Aufnahmen werden ohne erneute Videokodierung gespeichert. H.264 und H.265
bleiben unverändert, H.265 wird zusätzlich als `hvc1` gekennzeichnet, damit
Safari und iOS die Datei direkt abspielen können. Nur andere Videoformate
werden nach H.264 und browserfremdes Audio nach AAC konvertiert. Kann der
Mediathek-Player eine Aufnahme nicht direkt wiedergeben, etwa H.265 in
manchen Browsern, stellt der Server beim Abspielen automatisch eine
vollständig abgeschlossene, kompatible MP4-Datei bereit. Bei langen
4K-Aufnahmen kann diese erste Aufbereitung einige Zeit dauern; der Download
liefert immer das Original. Sie wird für
weitere Wiedergaben zwischengespeichert und beim Löschen der Originalaufnahme
ebenfalls entfernt; die Originaldatei selbst bleibt unverändert.

Während einer laufenden Aufnahme wird noch kein Mediathek-Eintrag veröffentlicht.
Beim Stoppen beendet die Anwendung FFmpeg kontrolliert, prüft die temporäre Datei
mit `ffprobe` und übernimmt sie erst danach atomar als sichtbare MP4-Datei. Eine
abgebrochene oder nicht validierbare Aufnahme wird nicht in der Mediathek
angeboten.

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
Der Mehrquellen-Runner wertet zusätzlich den maschinenlesbaren
FFmpeg-Fortschritt aus. Bleiben Bildzähler und Medienzeit trotz laufendem
Prozess stehen, beendet der Watchdog nach einer Starttoleranz nur den
betroffenen FFmpeg-Prozess und verbindet diese Quelle mit begrenztem Backoff
neu. Die übrigen Quellen laufen dabei weiter. Im Journal ist dieser Fall an
`kein Medienfortschritt` erkennbar:

```bash
sudo journalctl -u open-bos-streamer.service -f
```

Auf der Systemseite erscheint derselbe Zustand direkt an jeder Quelle. Für
verwaltete FFmpeg-Quellen werden FPS, Geschwindigkeit, seit dem Prozessstart
verworfene und duplizierte Frames sowie der Zeitpunkt des letzten echten
Medienfortschritts, CPU-Auslastung und Arbeitsspeicher in einer kompakten
Diagnosezeile angezeigt. Direkte
RTMP-Passthrough-Quellen haben keinen FFmpeg-Prozess und werden entsprechend
als MediaMTX-Empfang ausgewiesen.

Aus diesen Einzelwerten bildet die Systemseite außerdem eine gemeinsame
Gesundheitsbewertung pro Quelle. Eine zu geringe Echtzeitgeschwindigkeit,
kürzlich verworfene oder duplizierte Frames, fehlender Medienfortschritt und
mehrere Neustarts innerhalb kurzer Zeit werden dabei getrennt ausgewiesen.
Die Detailmeldung steht als Hinweis direkt am Status. Neustartanzahl und
Reconnect-Zustand gelten seit dem letzten Start des Streamer-Dienstes.

Fallen mehrere verwaltete Quellen gleichzeitig aus, bleiben ihre
exponentiellen Backoffs unabhängig. Der konkrete Wiederanlauf wird je
Quellen-ID leicht versetzt, damit nicht viele FFmpeg-Prozesse und
Netzwerkverbindungen im selben Moment neu aufgebaut werden.

Bei verwalteten RTMP-Quellen startet FFmpeg erst, nachdem MediaMTX den
Publisherpfad als verfügbar meldet. Eine ausgeschaltete Drohne oder ein noch
nicht gestarteter Testpublisher wird deshalb als „Wartet auf Eingangssignal“
angezeigt und erzeugt keine FFmpeg-Neustartschleife. Nach Eintreffen des
Signals beginnt die Verarbeitung typischerweise innerhalb einer Sekunde.

Die tiefergehende ffprobe-Paketdiagnose öffnet kurzzeitig einen zusätzlichen
Leser am Viewerpfad der ausgewählten Quelle. Sie wird ausschließlich über den
Button „Tiefendiagnose“ in der jeweiligen Quellenkarte gestartet, misst zwei
Sekunden und wird je Quelle eine Minute zwischengespeichert. Systemweit kann
nur eine solche Messung gleichzeitig laufen. Normale Dashboard-Aktualisierungen
und mehrere geöffnete Browser starten keine Probeprozesse mehr.

Das Ergebnis enthält tatsächliche und nominelle Bildrate, Bitrate,
Paketanzahl, rückwärtslaufende DTS-Zeitstempel, Jitter, maximale Paketlücke
und daraus abgeleitete Warnungen. Da der MediaMTX-Viewerpfad gemessen wird,
wird auch bei lokalen Capture Cards keine zweite Geräteverbindung geöffnet.
FFmpeg selbst läuft ohne interaktive Eingabe und protokolliert im
Normalbetrieb nur Warnungen und Fehler; die maschinenlesbaren
Fortschrittsdaten bleiben davon unberührt.

### Reproduzierbarer Mehrquellen-Dauertest

Für einen Test ohne mehrere Kameras kann auf einem separaten Rechner einmalig
ein synthetischer H.264/AAC-Clip erzeugt werden:

```bash
./scripts/generate-test-video.sh
```

Die erzeugte Datei liegt unter `testdata/open-bos-test-720p.mp4`, wird wegen
ihrer Größe nicht in Git aufgenommen und enthält 60 Sekunden 720p/25 FPS mit
einem synthetischen Tonsignal. Das H.264-Baseline-Signal wird ausdrücklich
ohne B-Frames erzeugt, da diese in WebRTC nicht unterstützt werden. Das
Publisher-Skript lehnt fremde Testclips mit erkannten B-Frames vor dem Start
ab. Anschließend werden die in den Einstellungen
angezeigten zwölfstelligen Publisher-Tokens in eine lokale Datei geschrieben:

```text
quelle-1=AbCdEf123456
quelle-2=GhIjKl789012
```

Die Datei muss vor dem Test geschützt werden. Sie wird weder vom Skript
verändert noch in das Projekt kopiert:

```bash
chmod 600 test-tokens.env
./scripts/multi-source-test.sh \
  --server ffw-stream.de \
  --tokens-file test-tokens.env \
  --count 4 \
  --duration 1800
```

Erlaubt sind 1, 4 oder 8 parallele Publisher. Jeder FFmpeg-Prozess liest den
Clip in Echtzeit und sendet ihn per Stream Copy, sodass der Testsender nur
wenig CPU benötigt. Die Starts werden um jeweils eine Sekunde versetzt.
`--duration 0` läuft bis `Strg+C`; Protokolle landen in `test-results/`.
Für einen aussagekräftigen Netzwerk- und Servertest sollte das Skript nicht
auf dem Open-BOS-Server, sondern auf einem Laptop oder zweiten Rechner laufen.
Die komplette Hilfe zeigt `./scripts/multi-source-test.sh --help`.
Ein abweichender FFmpeg-Pfad kann für portable oder isolierte Installationen
über `FFMPEG_BIN=/pfad/zu/ffmpeg` angegeben werden; ffprobe ist für die
Metadatenprüfung optional.

Vor einem längeren Lauf kann ein Superadmin auf der Systemseite das
„Browser-Testprotokoll“ starten. Es speichert alle fünf Sekunden CPU, RAM,
Temperatur, Signal- und Laufzeitstatus jeder Quelle sowie WebRTC-Bitrate,
Paketverlust, Jitter, Drop-Frames, letzten Bildfortschritt und automatische
Player-Reconnects. Die laufende Sitzung liegt ohne Publisher-Tokens im lokalen
Browserspeicher, übersteht einen Reload und kann anschließend als JSON
heruntergeladen werden. Nach spätestens 1000 Messpunkten werden die ältesten
Werte verworfen, damit der Browser nicht unkontrolliert Speicher belegt. Die
dauerhafte Speicherung erfolgt gebündelt alle 30 Sekunden, damit der Testmodus
selbst insbesondere auf Tablets möglichst wenig zusätzliche Last erzeugt.

Parallel sammelt auf dem VServer ein zweites Skript Ressourcenwerte und die
relevanten systemd-Journale im gleichen Zeitfenster:

```bash
sudo ./scripts/server-test-monitor.sh \
  --duration 3600 \
  --output /var/tmp/open-bos-test-8-quellen
```

Das Ziel enthält `system.log`, `services.log`, `kernel.log` und
`metadata.txt`. Ohne `--duration` läuft die Sammlung bis `Strg+C`. Damit sind
Publisher-, Server- und Browserseite eines Testlaufs getrennt und dauerhaft
auswertbar. Prozessargumente und Journale werden vor dem Speichern auf
URL-Passwörter und bekannte Token-/Passphrase-Parameter geprüft und maskiert.

Bei RTSP-Netzwerkkameras ist TCP die robuste Voreinstellung. Liefert die
Kamera trotz stabiler LAN-Verbindung kurze Aussetzer oder auffällige
Zeitstempel, kann pro Quelle „Copy mit Zeitstempel-Korrektur“ gewählt werden.
Für RTSP bleibt dabei – anders als beim aggressiven RTMP-Latenzmodus – ein
moderater FFmpeg-Eingangspuffer erhalten. Das glättet kleine Schwankungen,
kann die Latenz aber geringfügig erhöhen. Erst wenn die Systemdiagnose danach
weiterhin Drop-/Dup-Frames oder fehlenden Fortschritt meldet, sollte ein
Transcoding-Profil oder der Kamera-Substream geprüft werden.

## Oberfläche

- **Seitenleiste:** Übersicht, Livebilder, Karte, Wetter, Organisation,
  Medien, Einstellungen und System mit einheitlichen Symbolen. Am Desktop sitzt sie fest am linken Rand
  und lässt sich unten über „Einklappen“ auf Symbole reduzieren; der Browser
  merkt sich die Wahl. Auf Tablets zeigt sie nur Symbole. Auf Smartphones
  stehen Übersicht, Livebilder, Karte und Wetter in der Leiste am unteren Rand, alle
  weiteren Bereiche unter **„Mehr“** – so bleibt Platz für künftige Module.
- **Kopfzeile:** links der Seitentitel, rechts Uhrzeit, Status und
  Benutzermenü. Die Uhrzeit kommt vom Gerät, auf dem die Seite geöffnet ist.
- **Status:** eine einzige Anzeige „Einsatzbereit“ (grün) oder „Störung“
  (rot), sobald der Streaming-Server nicht erreichbar ist. Admins und
  Superadmins öffnen per Klick die Details (Streaming-Server, Prozessor,
  Arbeitsspeicher, Temperatur sofern ein Sensor vorhanden ist) mit einem
  Sprung zur Systemseite.
- **Übersicht:** Gesamtlage auf einen Blick – alle Drohnen und Kameras mit
  Status (online/offline), Wehr, Auflösung und laufender Aufnahme, dazu
  Flugwetter, Ereignisprotokoll und Weiterleitungen. Ein Klick auf eine Quelle
  öffnet die Livebilder.
- **Livebilder:** alle Videos der eigenen Organisation mit Vollbild,
  „Gastlink teilen“ sowie Snapshot und Aufnahme (Superadmin). Die Videos
  laufen nur, solange diese Seite geöffnet ist; Übersicht, Karte und Wetter
  verbrauchen dadurch keine Videodaten, was vor allem bei Mobilfunk zählt.
- **Benutzermenü:** Name und Rolle, Darstellung, „Als App installieren“ und
  Abmelden.
- **Darstellung:** Hell, Dunkel oder Auto. „Auto“ folgt der Einstellung des
  Geräts; die Wahl gilt pro Browser. Die Anmeldeseite folgt ebenfalls der
  Geräteeinstellung.
- **Ereignisprotokoll:** gemeinsames Protokoll des Servers für Admins und
  Superadmins (siehe „Betrieb“).
- **Smartphones:** kompakte Darstellung; die Speichern-Leiste der
  Einstellungen schwebt nur bei ungespeicherten Änderungen über dem Inhalt.
- **Als App installieren:** Die Oberfläche lässt sich auf iPhone, iPad und
  Android auf den Startbildschirm legen (Web-App, kein App-Store) und startet
  dann im Vollbild ohne Adressleiste. Auf Mobilgeräten erscheint oben auf der
  Übersicht einmalig ein Hinweis („Später“ blendet ihn für sieben Tage aus);
  die Anleitung für das jeweilige Gerät steht jederzeit im Benutzermenü. Unter
  Android bieten Chrome, Edge und Samsung Internet dort direkt „Jetzt
  installieren“ an, auf iPhone und iPad führt die Anleitung über Teilen →
  „Zum Home-Bildschirm“. In der installierten App und in der Gastansicht
  erscheint kein Hinweis.

## Benutzer, Organisationen und Rollen

Seit Version 0.21 bildet Open BOS den Landkreis mit seinen Feuerwehren ab.
Konten, Organisationen, Rollen und Fernpilotennachweise liegen in einer
SQLite-Datenbank (`config/open-bos.db`, nur für den Dienstbenutzer lesbar).
Änderungen am Datenmodell spielt `update.sh` beim Start automatisch ein
(Alembic). Eine Sicherung des Ordners `config/` genügt, um alles zu sichern.

### Ersteinrichtung

Beim ersten Aufruf nach der Installation fordert Open BOS dazu auf, das erste
Konto (Superadmin) anzulegen. Dafür ist ein einmaliger **Einrichtungscode**
nötig, damit niemand einen frisch installierten Server vor dem Betreiber
übernehmen kann. Der Installer zeigt den Code am Ende an; er steht außerdem in
`config/setup.code` und im Journal (`journalctl -u open-bos-stream`). Nach
der Einrichtung wird er gelöscht.

### Organisationsbaum

```text
Landkreis
├── Stadt-, Gemeinde- oder Samtgemeindefeuerwehr
│   └── Ortsfeuerwehren
└── Kreiseinheiten (bei Bedarf)
```

Im Menüpunkt **„Organisation“** (für Wehr-Admins, Kreis-Admins und
Superadmins) legen Admins Untereinheiten
an, benennen sie (mit Kurzname, z. B. „OF Hagen“), hinterlegen den Standort
der Wache, archivieren oder löschen leere Einheiten.

### Rollen

| Rolle | darf |
|---|---|
| **Zuschauer** | Livebilder, Karte und Wetter der eigenen Organisation |
| **Drohnenteam** | zusätzlich Gastlinks für Quellen der eigenen Organisation |
| **Wehr-Admin** | zusätzlich Quellen der Organisation einrichten, Konten und Rollen im eigenen Bereich verwalten, Untereinheiten anlegen |
| **Kreis-Admin** (Wehr-Admin auf Landkreisebene) | alles im Landkreis, dazu serverweite Einstellungen wie Wetter, Systemseite |
| **Superadmin** | technische Verwaltung: Streaming-Ausgänge, Medien, E-Mail, Speicher, Display, Webzugriff; vergibt die Superadmin-Rolle |

- Rollen **vererben sich nach unten**: Wer bei der Samtgemeindefeuerwehr
  Wehr-Admin ist, ist es auch in allen Ortsfeuerwehren darunter.
- Eine Person kann in mehreren Organisationen unterschiedliche Rollen haben.
- **Quellen gehören einer Wehr.** Konten sehen nur die Quellen ihrer
  Organisationen (samt Unterbaum) und Quellen ohne Zuordnung. Das gilt auch
  für Vollbild, WebRTC/HLS-Abrufe über Caddy und MediaMTX-Medientoken, das
  Ereignisprotokoll und die Gastlinks.
- Kontodaten (Name, Passwort, Sperre) ändert, wer **alle** Organisationen des
  Kontos verwaltet; Rollen im eigenen Bereich vergeben auch Wehr-Admins
  anderer Ebenen. Mindestens ein Superadmin bleibt immer erhalten.
- Nach einer Rollenänderung muss sich das Konto neu anmelden.
- **Fernpilotennachweise** (EU-Kompetenznachweis A1/A3, Fernpilotenzeugnis
  A2, STS) werden mit Nummer und Ablaufdatum je Konto erfasst; abgelaufene
  Nachweise sind rot markiert. Jede Person kann ihre eigenen Nachweise
  pflegen.
- Änderungen an Organisationen, Konten, Rollen und Nachweisen landen im
  Änderungsprotokoll der Datenbank.

### Übernahme beim Update auf 0.21

Beim ersten Start legt Open BOS den **„Landkreis“** und darunter die
Start-Organisation **„Meine Feuerwehr“** an (beide umbenennbar) und übernimmt
die bisherigen Konten aus `config/users.yaml`:

| bisher | danach |
|---|---|
| Superadmin | Superadmin und Kreis-Admin |
| Admin | Wehr-Admin der Start-Organisation |
| Viewer | Zuschauer der Start-Organisation |

Passwörter bleiben gültig. Die alte Datei wird als `users.yaml.importiert`
aufbewahrt. Bestehende Quellen und Gastlinks werden der Start-Organisation
zugeordnet.

Die Rechte werden sowohl in der Oberfläche als auch an jedem API-Endpunkt
geprüft. Jede Route deklariert ihre Mindestrolle (`auth/roles.py`); ein Test
schlägt fehl, sobald eine Route ohne Rolle hinzukommt.

Der lokale Kiosk erhält ausschließlich eine auf Loopback begrenzte
Viewer-Ansicht. Zusätzlich muss Chromium ein geheimes Ticket vorlegen, das der
Display-Dienst bei jedem Start neu erzeugt. Im normalen Chromium-Modus ist eine reguläre Anmeldung nötig,
wenn Einstellungen bedient werden sollen.
Eine vorübergehend nicht erreichbare Quelle wird unabhängig mit begrenztem
Backoff neu verbunden und unterbricht die übrigen Quellen nicht.

### Gastlinks für externe Stellen

Drohnenteams, Wehr-Admins und Superadmins erstellen in der Übersicht über
„Gastlink teilen“ für Quellen ihrer Organisation einen
Link für Stellen ohne eigenes Konto, z. B. Polizei oder Kreisbrandmeister:
Bezeichnung, freigegebene Quellen und Gültigkeit (2, 8, 24 oder höchstens
48 Stunden). Der Link wird einmalig mit QR-Code angezeigt und lässt sich
kopieren oder auf dem Handy direkt teilen.

Gäste sehen eine reduzierte Ansicht mit den freigegebenen Livebildern
(einschließlich Vollbild) und der Karte – ohne Ereignisprotokoll, Mediathek,
Einstellungen oder Systemangaben. Die Freigabe gilt pro Quelle auch für die
Videoabrufe selbst: Caddy (`/auth/media-access`) und die
MediaMTX-Leserprüfung lassen Gäste nur die Streams der gewählten Quellen
abrufen. Nach Ablauf oder Sperrung endet die Gastansicht innerhalb weniger
Sekunden.

Unter Einstellungen → „Gastlinks“ stehen alle Links der letzten sieben Tage
mit Ersteller, Ablauf und letztem Zugriff; jeder Admin kann aktive Links
sperren. Erstellen, Öffnen, Sperren und Ablauf eines Gastlinks
erscheinen zusätzlich im Ereignisprotokoll der Übersicht (für Admins und
Superadmins, Ereignisse der letzten 24 Stunden). Gespeichert wird nur ein Hash des Links in `config/guest_links.json`
(Rechte 0600). Öffnet ein angemeldeter Benutzer einen Gastlink im selben
Browser, bleibt seine Anmeldung erhalten; zum Ausprobieren eignet sich ein
privates Fenster.

## Aufnahmen und Snapshots

### Snapshots und Aufnahmen einer ausgewählten Quelle

Superadmins können in den Einstellungen eine aktive Quelle als Medienquelle
festlegen. Über den kompakten Balken oberhalb der Livebilder lassen sich für
diese Quelle Snapshots erstellen sowie Aufnahmen starten und stoppen. Während
einer Aufnahme zeigt der Balken die laufende Dauer; die beim Start verwendete
Quelle bleibt für diese Aufnahme fest gebunden.

Neue Dateien enthalten die Quellen-ID und einen Zeitstempel:

```text
snapshots/snapshot_quelle-1_20260801_201530.jpg
recordings/recording_quelle-1_20260801_201530.mp4
```

Die Dateien erscheinen automatisch in der vorhandenen Mediathek. Die
Bedienung, Medienseite sowie Snapshot- und Aufnahme-API bleiben ausschließlich
für Superadmins verfügbar. Ist die ausgewählte Quelle offline, bleiben die
Schaltflächen deaktiviert.

Aufnahmen lassen sich manuell und automatisch steuern:

- **Manuell:** Ein Superadmin startet und stoppt die Aufnahme der gewählten
  Medienquelle im Medienbalken.
- **Automatisch pro Quelle:** Unter „Automatisch aufnehmen“ werden die
  Quellen angehakt, die selbstständig aufnehmen sollen (höchstens vier). Die
  Anwendung überwacht jede dieser Quellen serverseitig: Sobald ihr Signal
  verfügbar ist, beginnt eine neue Aufnahme; endet das Signal, wird die Datei
  kontrolliert abgeschlossen und in der Mediathek veröffentlicht. Kehrt das
  Signal zurück, entsteht eine neue Aufnahme. Für automatisch aufnehmende
  Quellen sind manuelle Start-/Stopp-Befehle gesperrt.

Mehrere Aufnahmen laufen parallel, z. B. zwei Drohnen gleichzeitig oder eine
automatische Quelle und die manuelle Aufnahme einer anderen Medienquelle.
Eine feste Obergrenze für gleichzeitige Aufnahmen gibt es nicht; bei hoher
Serverlast erscheint ein Hinweis. Jede Videokachel
zeigt eine laufende Aufnahme mit Dauer an („● Auto-Aufnahme 12:34“). Da
H.264 und H.265 unverändert kopiert werden, kostet jede weitere Aufnahme kaum
Rechenleistung, aber entsprechend Speicherplatz. Bei Speichermangel werden
alle laufenden Aufnahmen sauber abgeschlossen.

Die Auswahl wird unmittelbar gespeichert und benötigt nicht den allgemeinen
Button „Änderungen speichern“. Dabei werden weder laufende Streams noch der
Mehrquellen-Streamer neu gestartet. Wird eine Quelle aus der Automatik
genommen, endet ihre automatisch gestartete Aufnahme. Konfigurationen bis
Version 0.18 mit „Aufnahme automatisch steuern“ werden beim Update
übernommen: Die bisherige Medienquelle nimmt weiter automatisch auf.

Ein einzelner kurzzeitig fehlender Statuswert beendet die Aufnahme nicht;
erst ein bestätigter Signalverlust löst den Abschluss aus. Die Automatik läuft
auch dann weiter, wenn keine Weboberfläche geöffnet ist.

### Speicherschutz und automatische Bereinigung

In den Einstellungen legt ein Superadmin unter „Speicherschutz“ zwei
Schwellwerte für den freien Speicher des Medienverzeichnisses fest:

- **Warnung** (Standard 15 % frei): Medienbalken und Systemseite weisen auf
  knappen Speicher hin.
- **Mindestgrenze** (Standard 5 % frei): Neue Aufnahmen und Snapshots werden
  gesperrt. Eine laufende Aufnahme wird sauber abgeschlossen, gespeichert und
  als „Wegen Speichermangel beendet“ gemeldet.

Optional kann „Älteste Medien bei Speichermangel löschen“ aktiviert werden.
Unterschreitet der freie Speicher dann die Mindestgrenze, löscht die Anwendung
die ältesten Aufnahmen und Snapshots, bis wieder zwei Prozentpunkte mehr als
die Mindestgrenze frei sind. Die Prüfung läuft alle 30 Sekunden sowie direkt
vor jeder neuen Aufnahme und jedem Snapshot, auch ohne geöffnete Oberfläche.
Jede Löschung erscheint im Anwendungsjournal; die letzte Bereinigung wird auf
der Systemseite angezeigt. Reicht das nicht aus, bleibt die Sperre bestehen.

Browserkompatible Wiedergabekopien in `recordings/.playback-cache` zählen
ebenfalls zum Speicherschutz. Sie werden bei Speichermangel immer zuerst
entfernt, unabhängig davon, ob die automatische Bereinigung aktiviert ist, da
sie beim nächsten Abspielen neu erzeugt werden können. Kopien, die sieben
Tage nicht abgespielt wurden, entfernt die Anwendung automatisch.

Wichtige Medien lassen sich in der Mediathek mit dem Schloss-Symbol als
„Behalten“ markieren. Sie werden nie automatisch gelöscht; manuelles Löschen
bleibt möglich. Die Markierung wird als versteckte Datei
`.<dateiname>.keep` neben der Mediendatei gespeichert.

## Betrieb

### Ereignisprotokoll

Das Ereignisprotokoll in der Übersicht wird vom Server geführt – auch dann,
wenn keine Oberfläche geöffnet ist – und ist für alle Admins und Superadmins
gleich. Erfasst werden unter anderem:

- Signal einer Quelle verfügbar oder verloren (Verlust nach zwei Prüfungen)
- Aufnahme gestartet, gespeichert, abgebrochen oder fehlgeschlagen
- Snapshot erstellt, Aufnahmen und Snapshots gelöscht
- Weiterleitung gestartet, gestoppt oder unerwartet beendet
- Streaming-Server nicht erreichbar, Speicher knapp oder erschöpft
- Konfiguration, Speicherschutz, Aufnahmesteuerung und Benachrichtigungen
  gespeichert
- Gastlinks erstellt, geöffnet, gesperrt oder abgelaufen
- versendete und fehlgeschlagene E-Mail-Benachrichtigungen
- Start und Ende des Dienstes

Bei Bedienaktionen steht der auslösende Benutzer am Ende der Meldung. Die
Einträge liegen in `config/event_log.jsonl`, überstehen Neustarts und
Updates und werden nach 30 Tagen automatisch entfernt. Die Oberfläche zeigt
beim Öffnen die letzten 200 Einträge und lädt danach nur neue nach.
„Leeren“ blendet die bisherigen Einträge nur im eigenen Browser aus; für
andere bleiben sie erhalten. Zuschauer und Gäste sehen das Protokoll nicht.

### E-Mail-Benachrichtigungen bei Störungen

In den Einstellungen richtet ein Superadmin unter „Benachrichtigungen“ den
Versand über einen eigenen SMTP-Server ein (Server, Port, Verschlüsselung,
Benutzername, Passwort, Absender und bis zu zehn Empfänger). „Speichern und
Testnachricht senden“ prüft die Einstellungen sofort.

Gemeldet werden, jeweils einzeln abschaltbar:

| Ereignis | Auslöser |
|---|---|
| Quelle ohne Signal | Eine Quelle, die gesendet hat, ist 30 s ohne Signal |
| Streaming-Server nicht erreichbar | MediaMTX ist 20 s nicht erreichbar |
| Speicher knapp oder erschöpft | Warnschwelle bzw. Mindestgrenze unterschritten |
| Aufnahme abgebrochen oder fehlgeschlagen | Streamabbruch, Speichermangel oder ungültige Datei |
| Streaming-Ausgang unerwartet beendet | FFmpeg einer Weiterleitung beendet sich selbst |
| Server gestartet | Dienststart, z. B. nach Neustart, Update oder Absturz |

Kurze Aussetzer werden abgewartet, jede Störung wird höchstens alle zehn
Minuten gemeldet, und nach einer gemeldeten Störung folgt eine Entwarnung.
Quellen, die seit dem Start nie gesendet haben (Drohne nicht in der Luft),
gelten nicht als gestört. Die Überwachung läuft im Server, auch ohne geöffnete
Oberfläche; der Versand erfolgt im Hintergrund und bremst Streaming und
Aufnahme nicht aus.

Das SMTP-Passwort steht nicht in `config/stream.yaml`, sondern in
`config/notifications.secret` (Rechte 0600) und wird nie an den Browser
ausgeliefert. Ziel-URLs in Fehlermeldungen von Weiterleitungen werden ohne
Stream-Schlüssel versendet. Admins sehen weder Mailserver noch Empfänger.

### Zeitzone

Server laufen oft in UTC. Damit Uhrzeiten in E-Mails, Gastlink-Meldungen,
Dateinamen von Aufnahmen und Snapshots sowie im Journal der deutschen Zeit
entsprechen, verwendet Open BOS Stream unabhängig von der Systemzeitzone
`Europe/Berlin` mit automatischer Sommer-/Winterzeit. Eine andere Zone lässt
sich über die Umgebungsvariable `OPEN_BOS_TIMEZONE` setzen, z. B. per
systemd-Override des Dienstes. Die Systemzeit des Servers bleibt unverändert;
wer auch Systemprotokolle in deutscher Zeit möchte, kann zusätzlich
`sudo timedatectl set-timezone Europe/Berlin` ausführen.

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

Admins und Superadmins können auf der Systemseite die letzten Meldungen von
Anwendung, Streamer und MediaMTX einsehen. Die Stream-Logansicht aktualisiert
sich bei geöffneter Ansicht alle fünf Sekunden; Tokens, URL-Zugangsdaten und
Passwörter werden serverseitig vor der Ausgabe verdeckt. Der zusätzlich
angebotene Server-Neustart bleibt ausschließlich Superadmins vorbehalten und
kann erst nach zwei aufeinanderfolgenden Bestätigungen zeitversetzt ausgelöst
werden. Beide Funktionen verwenden root-eigene Hilfsprogramme ohne frei
wählbare Befehle oder Parameter und werden auch über die API entsprechend der
Rolle geschützt.

Eine laufende Aufnahme wird durch einen separaten Wächter unabhängig von der
geöffneten Oberfläche überwacht. Endet FFmpeg unerwartet, etwa weil die
Streamverbindung abbricht, wird die temporäre MP4-Datei automatisch geprüft.
Eine gültige Teilaufnahme wird unmittelbar in der Mediathek veröffentlicht
und als durch Streamabbruch beendet gemeldet; eine nicht abspielbare Datei
wird entfernt und mit Fehlerstatus ausgewiesen. Im manuellen Aufnahmemodus
startet ein später zurückkehrender Stream keine neue Aufnahme. Nur der bewusst
aktivierte Automatikmodus startet bei einem erneuten Signal eine neue Datei.

Als zusätzliche Abstimmung steht `Copy-Reparatur · geringe Latenz` bereit.
Sie behält Stream Copy, Zeitstempelkorrektur und RTSP/TCP bei, reduziert aber
die Eingangsqueue von 512 auf 128 Pakete und begrenzt die RTSP-Verzögerung auf
100 ms. Das Profil eignet sich zum Vergleich bei nur leicht ruckelnden,
ansonsten stabilen Quellen. Bei stärkeren Paketlücken oder Bildaussetzern ist
`Copy mit Zeitstempel-Korrektur` weiterhin die robustere Einstellung.

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
pip install -r requirements-dev.txt
```

Tests ausführen:

```bash
PYTHONPATH=src python -m pytest -q
```

Auf GitHub laufen bei jedem Push auf `main` und bei Pull Requests automatisch
die Testsuite, eine Syntax- und Formatprüfung des Frontends
(`scripts/check-frontend.sh`) sowie eine Syntaxprüfung der Shell-Skripte
(`.github/workflows/tests.yml`). `requirements.txt` enthält nur die
Laufzeitpakete, `requirements-dev.txt` zusätzlich die Testwerkzeuge.

Die Funktionsübersicht auf der Anmeldeseite
(`src/open_bos_stream/static/docs/open-bos-stream-funktionsuebersicht.pdf`)
wird aus `docs/funktionsuebersicht.html` erzeugt, z. B. mit Chrome:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --no-pdf-header-footer --virtual-time-budget=15000 --print-to-pdf=src/open_bos_stream/static/docs/open-bos-stream-funktionsuebersicht.pdf "file://$PWD/docs/funktionsuebersicht.html"
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

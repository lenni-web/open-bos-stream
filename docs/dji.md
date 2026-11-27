# DJI-Anbindung einrichten (Cloud API, Pilot 2)

Live-Daten liefern Enterprise-Drohnen, die mit **DJI Pilot 2** geflogen
werden, zum Beispiel die Mavic 3E/3T mit der RC Pro Enterprise.
Consumer-Drohnen (DJI Fly) senden weiterhin nur ihr Livebild per RTMP.

> **Stand:** Die Anbindung ist nach der DJI-Dokumentation gebaut und mit
> nachgestellten Nachrichten getestet, aber noch nicht mit echter Hardware.

## Voraussetzungen

- Server-Profil mit HTTPS und eigener Domain
- DJI-Entwicklerkonto mit einer App vom Typ „Cloud API“
  (App-ID, App Key, Lizenz)
- Fernsteuerung mit Internetzugang (Hotspot oder LTE)

## Server

```bash
./scripts/update.sh
```

```bash
./scripts/configure-dji.sh
```

```bash
sudo nano /opt/open-bos-stream/config/dji.yaml
```

Dort `app_id`, `app_key` und `license` eintragen, speichern und neu starten:

```bash
sudo systemctl restart open-bos-stream.service
```

Die Datei enthält Zugangsdaten: nicht kopieren, nicht ins Repository.

## Fernsteuerung

1. In Pilot 2 die offene Plattform bzw. „Cloud-Dienste“ öffnen.
2. `https://<domain>/dji` eingeben und mit dem eigenen Konto anmelden
   (Drohnenteam oder höher).
3. In Open BOS unter „Drohnen“ die neuen Geräte benennen und einer Wehr
   zuordnen. Erst dann erscheinen die Daten auf der Karte der Wehr.

## Aufzeichnung

- Jede Nachricht von Drohne und Fernsteuerung wird unverändert gespeichert.
- Hat die Wehr genau einen laufenden Einsatz, wird die Drohne automatisch
  zugeordnet, sonst auf der Einsatzseite unter „Drohnendaten“.
- Bei Zuordnung werden bereits empfangene Daten ab Alarmzeit nachgetragen.
- Daten mit Einsatz bleiben, bis der Einsatz gelöscht wird. Daten ohne
  Einsatz werden nach 24 Stunden gelöscht.
- Download auf der Einsatzseite: Flugwerte (CSV) und alle Daten (JSONL).
- Nicht erfasst wird, was während eines Funklochs nicht gesendet wurde.

## Fehlersuche beim ersten Verbinden

- Die Seite `/dji` zeigt unten ein Verbindungsprotokoll.
- Broker: `sudo journalctl -u mosquitto -f`
- Anwendung: `sudo journalctl -u open-bos-stream -f`
- Lehnt Pilot 2 die Adresse ab, in `dji.yaml` `public_scheme: tcp`
  versuchen. Achtung: Der Port 8883 spricht TLS; eine unverschlüsselte
  Verbindung wird nicht eingerichtet.

## Abschalten oder Zugang wechseln

```bash
./scripts/configure-dji.sh --new-password
```

```bash
./scripts/configure-dji.sh --disable
```

Alle Fernsteuerungen teilen sich einen Broker-Zugang. Einzelne Geräte lassen
sich unter „Drohnen“ sperren; nach Verlust einer Fernsteuerung den
Zugang wechseln.

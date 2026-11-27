#!/bin/bash

# Richtet den MQTT-Broker (Mosquitto) für die DJI Cloud API ein.
#
#   ./scripts/configure-dji.sh                 einrichten bzw. aktualisieren
#   ./scripts/configure-dji.sh --new-password  Zugang der Fernsteuerungen wechseln
#   ./scripts/configure-dji.sh --disable       Anbindung abschalten
#
# Voraussetzung: Server-Profil mit HTTPS (Caddy) und aktueller Stand unter
# /opt/open-bos-stream (update.sh).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

BROKER_CONF="/etc/mosquitto/conf.d/open-bos.conf"
PASSWORD_FILE="/etc/mosquitto/open-bos.passwd"
ACL_FILE="/etc/mosquitto/open-bos.acl"
CERT_DIR="/etc/mosquitto/open-bos-certs"
CERT_HELPER="/usr/local/libexec/open-bos-stream/dji-certificate"
DJI_CONFIG="${TARGET_DIR}/config/dji.yaml"

NEW_PASSWORD=false
DISABLE=false
case "${1:-}" in
    "") ;;
    --new-password) NEW_PASSWORD=true ;;
    --disable) DISABLE=true ;;
    *) fail "Verwendung: $0 [--new-password | --disable]" ;;
esac

if [ "${DISABLE}" = true ]; then
    sudo systemctl disable --now open-bos-dji-certificate.path mosquitto.service || true
    sudo rm -f "${BROKER_CONF}"
    echo "Broker abgeschaltet. ${DJI_CONFIG} bleibt erhalten."
    sudo systemctl restart "${SERVICE_NAME}"
    exit 0
fi

[ -f "${SERVER_CONFIG_FILE}" ] || fail "Kein Server-Profil eingerichtet (${SERVER_CONFIG_FILE} fehlt)."
DOMAIN="$(awk -F= '$1 == "PUBLIC_DOMAIN" {print $2}' "${SERVER_CONFIG_FILE}")"
HTTPS="$(awk -F= '$1 == "HTTPS_ENABLED" {print $2}' "${SERVER_CONFIG_FILE}")"
[ "${HTTPS}" = "yes" ] && [ -n "${DOMAIN}" ] ||
    fail "Die DJI-Anbindung benötigt HTTPS mit eigener Domain."
[ -x "${VENV_DIR}/bin/python" ] || fail "${VENV_DIR} fehlt. Bitte zuerst update.sh ausführen."

SERVICE_ACCOUNT="$(systemctl show --property User --value "${SERVICE_NAME}")"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-${SERVICE_USER}}"

CERT_FILE="$(
    sudo find /var/lib/caddy -type f -name "${DOMAIN}.crt" 2>/dev/null | head -n 1
)"
[ -n "${CERT_FILE}" ] || fail "Noch kein Zertifikat für ${DOMAIN} bei Caddy gefunden."
KEY_FILE="${CERT_FILE%.crt}.key"

if ! command -v mosquitto >/dev/null 2>&1; then
    echo "Installiere Mosquitto aus den Debian-Paketquellen ..."
    sudo apt-get update
    sudo apt-get install --yes mosquitto
fi

# Zertifikat für Mosquitto kopieren, auch nach jeder Erneuerung durch Caddy.
helper_tmp="$(mktemp)"
unit_tmp="$(mktemp)"
trap 'rm -f "${helper_tmp}" "${unit_tmp}"' EXIT
cat > "${helper_tmp}" <<HELPER
#!/bin/sh
set -eu
install -d -o root -g mosquitto -m 0750 "${CERT_DIR}"
install -o mosquitto -g mosquitto -m 0644 "${CERT_FILE}" "${CERT_DIR}/server.crt"
install -o mosquitto -g mosquitto -m 0600 "${KEY_FILE}" "${CERT_DIR}/server.key"
if systemctl is-active --quiet mosquitto.service; then
    systemctl restart mosquitto.service
fi
HELPER
sudo install -d -m 0755 "$(dirname "${CERT_HELPER}")"
sudo install -o root -g root -m 0755 "${helper_tmp}" "${CERT_HELPER}"

cat > "${unit_tmp}" <<UNIT
[Unit]
Description=Open BOS: Zertifikat an den MQTT-Broker übergeben

[Service]
Type=oneshot
ExecStart=${CERT_HELPER}
UNIT
sudo install -m 0644 "${unit_tmp}" /etc/systemd/system/open-bos-dji-certificate.service
cat > "${unit_tmp}" <<UNIT
[Unit]
Description=Open BOS: Zertifikatserneuerung beobachten

[Path]
PathChanged=${CERT_FILE}

[Install]
WantedBy=multi-user.target
UNIT
sudo install -m 0644 "${unit_tmp}" /etc/systemd/system/open-bos-dji-certificate.path

# Zugänge in dji.yaml erzeugen bzw. beibehalten; DJI-Daten bleiben unberührt.
# Die Ausgabe sind die Zeilen der Broker-Passwortdatei (noch im Klartext).
sudo install -d -m 0755 "$(dirname "${DJI_CONFIG}")"
passwords_tmp="$(mktemp)"
trap 'rm -f "${helper_tmp}" "${unit_tmp}" "${passwords_tmp}"' EXIT
sudo "${VENV_DIR}/bin/python" - "${DJI_CONFIG}" "${DOMAIN}" "${NEW_PASSWORD}" > "${passwords_tmp}" <<'PYTHON'
import os
import secrets
import sys
from pathlib import Path

import yaml

path, domain, new_password = Path(sys.argv[1]), sys.argv[2], sys.argv[3] == "true"
data = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}
for key in ("app_id", "app_key", "license"):
    data.setdefault(key, "")
data.setdefault("platform_name", "Open BOS Drohnen")
data["public_host"] = data.get("public_host") or domain
data["server_username"] = "openbos"
data["pilot_username"] = "pilot"
if not data.get("server_password"):
    data["server_password"] = secrets.token_urlsafe(24)
if new_password or not data.get("pilot_password"):
    data["pilot_password"] = secrets.token_urlsafe(18)
descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(descriptor, "w", encoding="utf-8") as file:
    yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)
print(f"openbos:{data['server_password']}")
print(f"pilot:{data['pilot_password']}")
PYTHON
sudo chown "${SERVICE_ACCOUNT}" "${DJI_CONFIG}"
sudo chmod 0600 "${DJI_CONFIG}"

sudo install -o root -g mosquitto -m 0640 "${passwords_tmp}" "${PASSWORD_FILE}"
sudo mosquitto_passwd -U "${PASSWORD_FILE}"
sudo chown root:mosquitto "${PASSWORD_FILE}"
sudo chmod 0640 "${PASSWORD_FILE}"

cat > "${unit_tmp}" <<'ACL'
# Open BOS: Anwendung liest alles und antwortet.
user openbos
topic readwrite thing/#
topic readwrite sys/#

# Fernsteuerungen: eigene Daten senden, Antworten empfangen.
user pilot
topic write thing/product/+/osd
topic write thing/product/+/state
topic write thing/product/+/status
topic write thing/product/+/events
topic write thing/product/+/requests
topic write thing/product/+/services_reply
topic write thing/product/+/property/set_reply
topic write thing/product/+/drc/up
topic write sys/product/+/status
topic read sys/product/+/status_reply
topic read thing/product/+/status_reply
topic read thing/product/+/events_reply
topic read thing/product/+/requests_reply
topic read thing/product/+/services
topic read thing/product/+/property/set
topic read thing/product/+/drc/down
ACL
sudo install -o root -g mosquitto -m 0640 "${unit_tmp}" "${ACL_FILE}"

cat > "${unit_tmp}" <<CONF
# Von scripts/configure-dji.sh erzeugt.
per_listener_settings false
allow_anonymous false
password_file ${PASSWORD_FILE}
acl_file ${ACL_FILE}
message_size_limit 262144

# Anwendung auf diesem Server
listener 1883 127.0.0.1

# DJI-Fernsteuerungen (nur verschlüsselt)
listener 8883
certfile ${CERT_DIR}/server.crt
keyfile ${CERT_DIR}/server.key
CONF
sudo install -m 0644 "${unit_tmp}" "${BROKER_CONF}"

sudo systemctl daemon-reload
sudo "${CERT_HELPER}"
sudo systemctl enable --now open-bos-dji-certificate.path
sudo systemctl enable mosquitto.service
sudo systemctl restart mosquitto.service
sudo systemctl restart "${SERVICE_NAME}"

echo
echo "MQTT-Broker eingerichtet (TCP 8883 verschlüsselt)."
echo "Jetzt App-ID, App Key und Lizenz in ${DJI_CONFIG} eintragen:"
echo "  sudo nano ${DJI_CONFIG}"
echo "Danach in DJI Pilot 2 öffnen: https://${DOMAIN}/dji"

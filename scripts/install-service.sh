#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"
PROFILE="$(installation_profile)"
validate_installation_profile "${PROFILE}"

SOURCE_SERVICE_FILE="${SCRIPT_DIR}/open-bos-stream.service"
TARGET_SERVICE_FILE="/etc/systemd/system/open-bos-stream.service"
SOURCE_DISPLAY_SERVICE_FILE="${SCRIPT_DIR}/open-bos-display.service"
TARGET_DISPLAY_SERVICE_FILE="/etc/systemd/system/open-bos-display.service"
SOURCE_STREAMER_SERVICE_FILE="${SCRIPT_DIR}/open-bos-streamer.service"
TARGET_STREAMER_SERVICE_FILE="/etc/systemd/system/open-bos-streamer.service"
SOURCE_WEB_PROXY_SOCKET_FILE="${SCRIPT_DIR}/open-bos-web-proxy.socket"
TARGET_WEB_PROXY_SOCKET_FILE="/etc/systemd/system/open-bos-web-proxy.socket"
SOURCE_WEB_PROXY_SERVICE_FILE="${SCRIPT_DIR}/open-bos-web-proxy.service"
TARGET_WEB_PROXY_SERVICE_FILE="/etc/systemd/system/open-bos-web-proxy.service"
SOURCE_MEDIAMTX_SERVICE_FILE="${SCRIPT_DIR}/mediamtx.service"
TARGET_MEDIAMTX_SERVICE_FILE="/etc/systemd/system/mediamtx.service"
SOURCE_MEDIAMTX_CONFIG="${PROJECT_DIR}/config/mediamtx.${PROFILE}.yml"
TARGET_MEDIAMTX_CONFIG="${PROFILE_DIR}/mediamtx.yml"
SOURCE_SUDOERS_FILE="${SCRIPT_DIR}/open-bos-stream-sudoers"
SOURCE_SERVER_SUDOERS_FILE="${SCRIPT_DIR}/open-bos-stream-server-sudoers"
TARGET_SUDOERS_FILE="/etc/sudoers.d/open-bos-stream"

if [ -z "${SERVICE_USER}" ] || [ -z "${SERVICE_GROUP}" ]; then
    echo "FEHLER: User oder Group konnte nicht aus der Service-Datei gelesen werden."
    exit 1
fi

if [ ! -f "${TARGET_DIR}/requirements.txt" ]; then
    echo "FEHLER: ${TARGET_DIR}/requirements.txt wurde nicht gefunden."
    echo "Bitte zuerst das Deployment ausführen."
    exit 1
fi

echo
echo "========================================"
echo " Open BOS Stream Service-Installation"
echo "========================================"
echo

echo "Service-Benutzer:"
echo "  ${SERVICE_USER}:${SERVICE_GROUP}"
echo

echo "Installationsprofil: ${PROFILE}"

if [ ! -x "/usr/local/bin/mediamtx" ]; then
    fail "MediaMTX fehlt unter /usr/local/bin/mediamtx. Bitte install-mediamtx.sh ausführen."
fi

DISPLAY_GROUPS=()
for group in video; do
    if getent group "${group}" >/dev/null 2>&1; then
        DISPLAY_GROUPS+=("${group}")
    fi
done
if [ "${PROFILE}" = "local" ]; then
    for group in render input; do
        if getent group "${group}" >/dev/null 2>&1; then
            DISPLAY_GROUPS+=("${group}")
        fi
    done
fi

if [ "${#DISPLAY_GROUPS[@]}" -gt 0 ]; then
    DISPLAY_GROUP_LIST="$(
        IFS=,
        echo "${DISPLAY_GROUPS[*]}"
    )"
    sudo usermod \
        --append \
        --groups "${DISPLAY_GROUP_LIST}" \
        "${SERVICE_USER}"
fi

echo "Stelle Besitzrechte des Installationsverzeichnisses sicher ..."

sudo chown "${SERVICE_USER}:${SERVICE_GROUP}" "${TARGET_DIR}"

echo
echo "Erstelle oder aktualisiere Produktions-Venv ..."

if [ ! -x "${VENV_DIR}/bin/python" ]; then
    sudo -u "${SERVICE_USER}" \
        python3 -m venv "${VENV_DIR}"
fi

sudo -u "${SERVICE_USER}" \
    "${VENV_DIR}/bin/python" \
    -m pip install \
    --upgrade \
    pip \
    setuptools \
    wheel

sudo -u "${SERVICE_USER}" \
    "${VENV_DIR}/bin/python" \
    -m pip install \
    --requirement "${TARGET_DIR}/requirements.txt"

sudo -u "${SERVICE_USER}" \
    "${VENV_DIR}/bin/python" \
    -m pip install \
    --no-deps \
    "${TARGET_DIR}"

echo
echo "Installiere systemd-Service ..."

sudo install \
    --mode=0644 \
    "${SOURCE_SERVICE_FILE}" \
    "${TARGET_SERVICE_FILE}"

if [ "${PROFILE}" = "local" ]; then
    sudo install \
        --mode=0644 \
        "${SOURCE_DISPLAY_SERVICE_FILE}" \
        "${TARGET_DISPLAY_SERVICE_FILE}"
    if [ -f "${SERVER_CONFIG_FILE}" ]; then
        sudo systemctl disable --now caddy.service >/dev/null 2>&1 || true
        sudo rm -f \
            /etc/systemd/system/open-bos-stream.service.d/server-bind.conf
    fi
else
    sudo systemctl disable --now open-bos-display.service >/dev/null 2>&1 || true
    sudo rm -f "${TARGET_DISPLAY_SERVICE_FILE}"

fi

sudo install -d -m 0755 "${PROFILE_DIR}"
sudo install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0755 \
    /var/lib/open-bos-stream
sudo install -m 0644 \
    "${SOURCE_MEDIAMTX_CONFIG}" \
    "${TARGET_MEDIAMTX_CONFIG}"
sudo install -m 0644 \
    "${SOURCE_MEDIAMTX_SERVICE_FILE}" \
    "${TARGET_MEDIAMTX_SERVICE_FILE}"

sudo install \
    --mode=0644 \
    "${SOURCE_STREAMER_SERVICE_FILE}" \
    "${TARGET_STREAMER_SERVICE_FILE}"

if [ "${PROFILE}" = "local" ]; then
    sudo install \
        --mode=0644 \
        "${SOURCE_WEB_PROXY_SOCKET_FILE}" \
        "${TARGET_WEB_PROXY_SOCKET_FILE}"
    sudo install \
        --mode=0644 \
        "${SOURCE_WEB_PROXY_SERVICE_FILE}" \
        "${TARGET_WEB_PROXY_SERVICE_FILE}"
else
    sudo systemctl disable --now open-bos-web-proxy.socket >/dev/null 2>&1 || true
    sudo rm -f \
        "${TARGET_WEB_PROXY_SOCKET_FILE}" \
        "${TARGET_WEB_PROXY_SERVICE_FILE}"
fi

sudo install \
    --mode=0440 \
    "$(
        if [ "${PROFILE}" = "server" ]; then
            printf '%s' "${SOURCE_SERVER_SUDOERS_FILE}"
        else
            printf '%s' "${SOURCE_SUDOERS_FILE}"
        fi
    )" \
    "${TARGET_SUDOERS_FILE}"

sudo visudo \
    --check \
    --file="${TARGET_SUDOERS_FILE}"

sudo systemctl daemon-reload

sudo systemctl enable mediamtx.service

# Der Display-Dienst wird bewusst niemals für den Boot aktiviert.
sudo systemctl disable \
    open-bos-display.service \
    >/dev/null 2>&1 || true

WEB_ACCESS_ENABLED="$(
    sudo -u "${SERVICE_USER}" \
        "${VENV_DIR}/bin/python" \
        -c '
import sys
import yaml

with open(sys.argv[1], encoding="utf-8") as config_file:
    config = yaml.safe_load(config_file) or {}

print("yes" if config.get("web_access", {}).get("enabled", False) else "no")
' \
        "${TARGET_DIR}/config/stream.yaml"
)"

if [ "${PROFILE}" = "server" ]; then
    echo "Server-Profil: Port 80 bleibt für einen HTTPS-Proxy reserviert."
elif [ "${WEB_ACCESS_ENABLED}" = "yes" ]; then
    echo "Standard-Webzugriff aktivieren ..."
    sudo systemctl enable open-bos-web-proxy.socket
    if ! sudo systemctl restart open-bos-web-proxy.socket; then
        echo "WARNUNG: Port 80 konnte nicht aktiviert werden."
        echo "Die Oberfläche bleibt über Port 8000 erreichbar."
    fi
else
    sudo systemctl disable \
        --now \
        open-bos-web-proxy.socket \
        >/dev/null 2>&1 || true
    sudo systemctl stop \
        open-bos-web-proxy.service \
        >/dev/null 2>&1 || true
fi

PASSTHROUGH_ENABLED="$(
    sudo -u "${SERVICE_USER}" \
        "${VENV_DIR}/bin/python" \
        -c '
import sys
import yaml

with open(sys.argv[1], encoding="utf-8") as config_file:
    config = yaml.safe_load(config_file) or {}

sources = [
    source
    for source in config.get("sources", [])
    if source.get("enabled", True)
]
managed = any(
    not (
        source.get("type") == "rtmp"
        and source.get("profile", "direct") == "direct"
    )
    for source in sources
)
if not sources:
    managed = not (
        config.get("stream", {}).get("passthrough", False)
        and config.get("encoder", {}).get("codec") == "copy"
        and config.get("input", {}).get("type") in {
            "rtmp",
            "rtsp",
            "srt",
            "udp",
            "http",
            "hls",
        }
    )
print("no" if managed else "yes")
' \
        "${TARGET_DIR}/config/stream.yaml"
)"

if [ "${PASSTHROUGH_ENABLED}" = "yes" ]; then
    echo "Passthrough aktiv: internen FFmpeg-Streamer deaktivieren ..."

    sudo systemctl disable \
        --now \
        open-bos-streamer.service \
        >/dev/null 2>&1 || true
else
    echo "Verwalteter Stream aktiv: FFmpeg-Streamer einschalten ..."

    sudo systemctl enable \
        --now \
        open-bos-streamer.service
fi

sudo systemctl enable open-bos-stream.service
sudo systemctl restart open-bos-stream.service
sudo systemctl restart mediamtx.service

echo
echo "Service wurde installiert und neu gestartet."

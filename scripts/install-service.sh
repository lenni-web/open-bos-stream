#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

SOURCE_SERVICE_FILE="${SCRIPT_DIR}/open-bos-stream.service"
TARGET_SERVICE_FILE="/etc/systemd/system/open-bos-stream.service"
SOURCE_DISPLAY_SERVICE_FILE="${SCRIPT_DIR}/open-bos-display.service"
TARGET_DISPLAY_SERVICE_FILE="/etc/systemd/system/open-bos-display.service"
SOURCE_STREAMER_SERVICE_FILE="${SCRIPT_DIR}/open-bos-streamer.service"
TARGET_STREAMER_SERVICE_FILE="/etc/systemd/system/open-bos-streamer.service"
SOURCE_SUDOERS_FILE="${SCRIPT_DIR}/open-bos-stream-sudoers"
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

sudo install \
    --mode=0644 \
    "${SOURCE_DISPLAY_SERVICE_FILE}" \
    "${TARGET_DISPLAY_SERVICE_FILE}"

sudo install \
    --mode=0644 \
    "${SOURCE_STREAMER_SERVICE_FILE}" \
    "${TARGET_STREAMER_SERVICE_FILE}"

sudo install \
    --mode=0440 \
    "${SOURCE_SUDOERS_FILE}" \
    "${TARGET_SUDOERS_FILE}"

sudo visudo \
    --check \
    --file="${TARGET_SUDOERS_FILE}"

sudo systemctl daemon-reload

# Der Display-Dienst wird bewusst niemals für den Boot aktiviert.
sudo systemctl disable \
    open-bos-display.service \
    >/dev/null 2>&1 || true

PASSTHROUGH_ENABLED="$(
    sudo -u "${SERVICE_USER}" \
        "${VENV_DIR}/bin/python" \
        -c '
import sys
import yaml

with open(sys.argv[1], encoding="utf-8") as config_file:
    config = yaml.safe_load(config_file) or {}

print(
    "yes"
    if (
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
    else "no"
)
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

echo
echo "Service wurde installiert und neu gestartet."

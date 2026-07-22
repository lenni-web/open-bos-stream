#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

SOURCE_SERVICE_FILE="${SCRIPT_DIR}/open-bos-stream.service"
TARGET_SERVICE_FILE="/etc/systemd/system/open-bos-stream.service"

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

echo
echo "Installiere systemd-Service ..."

sudo install \
    --mode=0644 \
    "${SOURCE_SERVICE_FILE}" \
    "${TARGET_SERVICE_FILE}"

sudo systemctl daemon-reload
sudo systemctl enable open-bos-stream.service
sudo systemctl restart open-bos-stream.service

echo
echo "Service wurde installiert und neu gestartet."
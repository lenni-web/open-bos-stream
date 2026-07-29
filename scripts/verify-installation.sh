#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"
SERVICE_NAME="open-bos-stream.service"
CHECK_URL="http://127.0.0.1:8000/api/map/layers"

FAILED=0

check_success() {
    echo "  OK: $1"
}

check_failure() {
    echo "  FEHLER: $1"
    FAILED=1
}

echo
echo "========================================"
echo " Open BOS Stream Installationsprüfung"
echo "========================================"
echo

echo "Prüfe Verzeichnisstruktur ..."

for directory in \
    config \
    mapdata \
    recordings \
    snapshots \
    src
do
    if [ -d "${TARGET_DIR}/${directory}" ]; then
        check_success "${TARGET_DIR}/${directory}"
    else
        check_failure "${TARGET_DIR}/${directory} fehlt"
    fi
done

echo
echo "Prüfe Produktions-Venv ..."

if [ -x "${VENV_DIR}/bin/python" ]; then
    check_success "Python-Venv vorhanden"
    "${VENV_DIR}/bin/python" --version
else
    check_failure "Python-Venv fehlt"
fi

echo
echo "Prüfe Python-Module ..."

if [ -x "${VENV_DIR}/bin/python" ] &&
    "${VENV_DIR}/bin/python" \
        -c "import fastapi, uvicorn, open_bos_stream" \
        >/dev/null 2>&1
then
    check_success "FastAPI, Uvicorn und Open BOS Stream importierbar"
else
    check_failure "Python-Module konnten nicht importiert werden"
fi

echo
echo "Prüfe systemd-Service ..."

if systemctl is-enabled "${SERVICE_NAME}" >/dev/null 2>&1; then
    check_success "Service ist aktiviert"
else
    check_failure "Service ist nicht aktiviert"
fi

if systemctl is-active "${SERVICE_NAME}" >/dev/null 2>&1; then
    check_success "Service läuft"
else
    check_failure "Service läuft nicht"

    echo
    systemctl status "${SERVICE_NAME}" --no-pager || true
fi

echo
echo "Prüfe HTTP-Endpunkt ..."

HTTP_OK=0

for attempt in {1..10}; do
    if curl \
        --silent \
        --show-error \
        --fail \
        --max-time 5 \
        "${CHECK_URL}" \
        >/dev/null 2>&1
    then
        HTTP_OK=1
        break
    fi

    echo "  Warte auf Anwendung (${attempt}/10) ..."
    sleep 2
done

if [ "${HTTP_OK}" -eq 1 ]; then
    check_success "${CHECK_URL} antwortet"
else
    check_failure "${CHECK_URL} ist nicht erreichbar"
fi

echo
echo "Prüfe optionalen Display-Dienst ..."

if [ -f "/etc/systemd/system/open-bos-streamer.service" ]; then
    check_success "Streamer-Service installiert"
else
    check_failure "Streamer-Service fehlt"
fi

if [ -f "/etc/systemd/system/open-bos-display.service" ]; then
    check_success "Display-Service installiert"
else
    check_failure "Display-Service fehlt"
fi

DISPLAY_ENABLEMENT="$(
    systemctl is-enabled \
        open-bos-display.service \
        2>/dev/null || true
)"

if [ "${DISPLAY_ENABLEMENT}" = "enabled" ] ||
    [ "${DISPLAY_ENABLEMENT}" = "enabled-runtime" ]
then
    check_failure "Display-Service darf nicht beim Boot aktiviert sein"
else
    check_success \
        "Display-Service startet nicht automatisch beim Boot (${DISPLAY_ENABLEMENT:-disabled})"
fi

if command -v chromium >/dev/null 2>&1 ||
    command -v chromium-browser >/dev/null 2>&1
then
    check_success "Chromium vorhanden"
else
    check_failure "Chromium fehlt"
fi

echo

if [ "${FAILED}" -ne 0 ]; then
    echo "========================================"
    echo " Installation unvollständig"
    echo "========================================"
    exit 1
fi

echo "========================================"
echo " Installation erfolgreich geprüft"
echo "========================================"

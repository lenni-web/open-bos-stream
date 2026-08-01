#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"
PROFILE="$(installation_profile)"
validate_installation_profile "${PROFILE}"
SERVICE_NAME="open-bos-stream.service"
# Der Auth-Status ist absichtlich öffentlich und bestätigt sowohl HTTP als
# auch die initialisierte Anwendung, ohne geschützte Fachdaten offenzulegen.
CHECK_URL="http://127.0.0.1:8000/auth/status"

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
echo "Profil: ${PROFILE}"
echo "Dienstidentität: ${SERVICE_USER}:${SERVICE_GROUP}"
echo

if id "${SERVICE_USER}" >/dev/null 2>&1; then
    check_success "Dienstbenutzer ${SERVICE_USER} vorhanden"
else
    check_failure "Dienstbenutzer ${SERVICE_USER} fehlt"
fi
if getent group "${SERVICE_GROUP}" >/dev/null 2>&1; then
    check_success "Dienstgruppe ${SERVICE_GROUP} vorhanden"
else
    check_failure "Dienstgruppe ${SERVICE_GROUP} fehlt"
fi
if [ -f "${INSTALL_CONFIG_FILE}" ]; then
    check_success "Installationsparameter persistent gespeichert"
else
    check_failure "${INSTALL_CONFIG_FILE} fehlt"
fi

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

UNIT_USER="$(systemctl show "${SERVICE_NAME}" -p User --value 2>/dev/null || true)"
UNIT_GROUP="$(systemctl show "${SERVICE_NAME}" -p Group --value 2>/dev/null || true)"
if [ "${UNIT_USER}" = "${SERVICE_USER}" ] &&
    [ "${UNIT_GROUP}" = "${SERVICE_GROUP}" ]; then
    check_success "Service verwendet ${SERVICE_USER}:${SERVICE_GROUP}"
else
    check_failure "Service verwendet ${UNIT_USER:-?}:${UNIT_GROUP:-?} statt ${SERVICE_USER}:${SERVICE_GROUP}"
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

if [ "${PROFILE}" = "local" ] &&
    [ -f "/etc/systemd/system/open-bos-display.service" ]; then
    check_success "Display-Service installiert"
elif [ "${PROFILE}" = "server" ] &&
    [ ! -f "/etc/systemd/system/open-bos-display.service" ]; then
    check_success "Server-Profil ohne Display-Service"
else
    check_failure "Display-Service passt nicht zum Profil"
fi

if [ "${PROFILE}" = "server" ]; then
    check_success "Port 80 bleibt für den späteren HTTPS-Proxy reserviert"
elif [ -f "/etc/systemd/system/open-bos-web-proxy.socket" ] &&
    [ -f "/etc/systemd/system/open-bos-web-proxy.service" ]
then
    check_success "Optionaler Standard-Webzugriff installiert"
else
    check_failure "Units für den Standard-Webzugriff fehlen"
fi

if [ "${PROFILE}" = "local" ]; then
    WEB_PROXY_STATE="$(
        systemctl is-active open-bos-web-proxy.socket 2>/dev/null || true
    )"
    check_success \
        "Standard-Webzugriff: ${WEB_PROXY_STATE:-inaktiv}; Port 8000 bleibt verfügbar"
fi

if [ "${PROFILE}" = "local" ]; then
    DISPLAY_ENABLEMENT="$(
        systemctl is-enabled \
            open-bos-display.service \
            2>/dev/null || true
    )"
    if [ "${DISPLAY_ENABLEMENT}" = "enabled" ] ||
        [ "${DISPLAY_ENABLEMENT}" = "enabled-runtime" ]; then
        check_failure "Display-Service darf nicht beim Boot aktiviert sein"
    else
        check_success "Display-Service startet nicht automatisch beim Boot"
    fi

    if command -v chromium >/dev/null 2>&1 ||
        command -v chromium-browser >/dev/null 2>&1; then
        check_success "Chromium vorhanden"
    else
        check_failure "Chromium fehlt"
    fi

    for command in labwc dbus-run-session; do
        if command -v "${command}" >/dev/null 2>&1; then
            check_success "${command} vorhanden"
        else
            check_failure "${command} fehlt"
        fi
    done

    if systemctl cat seatd.service >/dev/null 2>&1; then
        check_success "seatd-Service vorhanden"
    else
        check_failure "seatd-Service fehlt"
    fi
fi

if [ -x /usr/local/bin/mediamtx ]; then
    check_success "MediaMTX-Binärdatei unter /usr/local/bin vorhanden"
    check_success "MediaMTX-Version: $(/usr/local/bin/mediamtx --version 2>&1 | head -n 1)"
else
    check_failure "MediaMTX-Binärdatei fehlt unter /usr/local/bin"
fi

if systemctl is-active mediamtx.service >/dev/null 2>&1; then
    check_success "MediaMTX läuft"
else
    check_failure "MediaMTX läuft nicht"
fi
if [ -f "${PROFILE_DIR}/mediamtx.yml" ]; then
    check_success "MediaMTX-Konfiguration vorhanden"
    if grep -q '^authMethod: http$' "${PROFILE_DIR}/mediamtx.yml" &&
        grep -q '/internal/mediamtx/auth' "${PROFILE_DIR}/mediamtx.yml"; then
        check_success "RTMP-Publisher-Token-Schutz aktiv"
    else
        check_failure "RTMP-Publisher-Token-Schutz fehlt"
    fi
else
    check_failure "MediaMTX-Konfiguration fehlt"
fi

if [ "${PROFILE}" = "server" ]; then
    if [ -f "${SERVER_CONFIG_FILE}" ]; then
        check_success "Serverzugriff-Konfiguration vorhanden"
        HTTPS_ENABLED="$(
            awk -F= '$1 == "HTTPS_ENABLED" {print $2}' \
                "${SERVER_CONFIG_FILE}"
        )"
        WEBRTC_MODE="$(
            awk -F= '$1 == "WEBRTC_MODE" {print $2}' \
                "${SERVER_CONFIG_FILE}"
        )"
        FIREWALL_MODE="$(
            awk -F= '$1 == "FIREWALL_MODE" {print $2}' \
                "${SERVER_CONFIG_FILE}"
        )"

        if [ "${HTTPS_ENABLED}" = "yes" ]; then
            if systemctl is-active caddy.service >/dev/null 2>&1; then
                check_success "Caddy/HTTPS läuft"
            else
                check_failure "Caddy/HTTPS läuft nicht"
            fi
            if grep -q "127.0.0.1:8889" \
                "${PROFILE_DIR}/mediamtx.yml"; then
                check_success "WHEP wird ausschließlich über Caddy veröffentlicht"
            else
                check_failure "WHEP lauscht trotz HTTPS nicht nur lokal"
            fi
        else
            check_success "HTTPS ist bewusst deaktiviert"
        fi

        if [ "${WEBRTC_MODE}" = "public" ]; then
            if grep -q "^webrtcAdditionalHosts:" \
                "${PROFILE_DIR}/mediamtx.yml"; then
                check_success "Öffentlicher WebRTC-Host konfiguriert"
            else
                check_failure "Öffentlicher WebRTC-Host fehlt"
            fi
        fi

        if [ "${FIREWALL_MODE}" = "configure" ]; then
            if sudo ufw status 2>/dev/null | grep -q "^Status: active"; then
                check_success "UFW ist aktiv"
            else
                check_failure "UFW sollte aktiv sein"
            fi
        else
            check_success "Host-Firewall wird extern verwaltet"
        fi
    else
        check_failure "Serverzugriff-Konfiguration fehlt"
    fi
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

#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

PROFILE=""
SERVER_ARGS=()
MEDIAMTX_MODE="auto"
MEDIAMTX_VERSION=""
MEDIAMTX_ARCHIVE=""
SERVICE_USER_OVERRIDE=""
SERVICE_GROUP_OVERRIDE=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --profile)
            PROFILE="${2:-}"
            shift 2
            ;;
        --domain|--webrtc|--firewall)
            SERVER_ARGS+=("$1" "${2:-}")
            shift 2
            ;;
        --https|--no-https)
            SERVER_ARGS+=("$1")
            shift
            ;;
        --install-mediamtx)
            MEDIAMTX_MODE="install"
            shift
            ;;
        --no-install-mediamtx)
            MEDIAMTX_MODE="external"
            shift
            ;;
        --mediamtx-version)
            MEDIAMTX_VERSION="${2:-}"
            shift 2
            ;;
        --mediamtx-archive)
            MEDIAMTX_ARCHIVE="${2:-}"
            shift 2
            ;;
        --service-user)
            SERVICE_USER_OVERRIDE="${2:-}"
            shift 2
            ;;
        --service-group)
            SERVICE_GROUP_OVERRIDE="${2:-}"
            shift 2
            ;;
        *)
            echo "Verwendung: $0 [--profile local|server] [--service-user USER] [--service-group GRUPPE] [MediaMTX-Optionen] [Serveroptionen]" >&2
            exit 2
            ;;
    esac
done

if [ -z "${PROFILE}" ] && [ -t 0 ]; then
    echo "Installationsprofil:"
    echo "  1) Lokal / Raspberry Pi (Capture Card und lokales Display)"
    echo "  2) Server (Netzwerkquellen ohne lokales Display)"
    read -r -p "Auswahl [1]: " PROFILE_CHOICE
    case "${PROFILE_CHOICE:-1}" in
        1|local) PROFILE="local" ;;
        2|server) PROFILE="server" ;;
        *) fail "Ungültige Profilauswahl." ;;
    esac
fi
PROFILE="${PROFILE:-local}"
validate_installation_profile "${PROFILE}"
export OPEN_BOS_PROFILE="${PROFILE}"
if [ -n "${SERVICE_USER_OVERRIDE}" ]; then
    export OPEN_BOS_SERVICE_USER="${SERVICE_USER_OVERRIDE}"
fi
if [ -n "${SERVICE_GROUP_OVERRIDE}" ]; then
    export OPEN_BOS_SERVICE_GROUP="${SERVICE_GROUP_OVERRIDE}"
fi
validate_service_identity \
    "${OPEN_BOS_SERVICE_USER:-${SERVICE_USER}}" \
    "${OPEN_BOS_SERVICE_GROUP:-${SERVICE_GROUP}}"

sudo install -d -m 0755 "${PROFILE_DIR}"
printf '%s\n' "${PROFILE}" | sudo tee "${PROFILE_FILE}" >/dev/null
sudo chmod 0644 "${PROFILE_FILE}"

echo
echo "========================================"
echo " Open BOS Stream Installer"
echo "========================================"
echo
echo "Profil: ${PROFILE}"
if [ "$(id -u)" -eq 0 ]; then
    echo "Installer läuft als root; Dienste verwenden ein unprivilegiertes Konto."
fi
echo

echo "[1/9] Systemabhängigkeiten"
"${SCRIPT_DIR}/install-dependencies.sh"

echo
echo "[2/9] Dienstbenutzer"
"${SCRIPT_DIR}/ensure-service-user.sh"

echo
echo "[3/9] MediaMTX"
MEDIAMTX_ARGS=(--mode "${MEDIAMTX_MODE}")
if [ -n "${MEDIAMTX_VERSION}" ]; then
    MEDIAMTX_ARGS+=(--version "${MEDIAMTX_VERSION}")
fi
if [ -n "${MEDIAMTX_ARCHIVE}" ]; then
    MEDIAMTX_ARGS+=(--archive "${MEDIAMTX_ARCHIVE}")
fi
if [ -t 0 ]; then
    MEDIAMTX_ARGS+=(--interactive)
else
    MEDIAMTX_ARGS+=(--non-interactive)
fi
"${SCRIPT_DIR}/install-mediamtx.sh" "${MEDIAMTX_ARGS[@]}"

echo
echo "[4/9] Deployment"
"${SCRIPT_DIR}/deploy.sh"

echo
echo "[5/9] Deployment-Information"

"${SCRIPT_DIR}/write-deployment-info.sh"

echo
echo "[6/9] Laufzeitumgebung"
"${SCRIPT_DIR}/initialize-runtime.sh"

echo
echo "[7/9] Service"
"${SCRIPT_DIR}/install-service.sh"

echo
echo "[8/9] Serverzugriff"
if [ "${PROFILE}" = "server" ]; then
    "${SCRIPT_DIR}/configure-server-access.sh" "${SERVER_ARGS[@]}"
else
    echo "Lokales Profil: Serverzugriff übersprungen."
fi

echo
echo "[9/9] Installation prüfen"
"${SCRIPT_DIR}/verify-installation.sh"

echo
echo "========================================"
echo " Open BOS Stream erfolgreich installiert"
echo "========================================"

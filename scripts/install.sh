#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

PROFILE=""
SERVER_ARGS=()
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
        *)
            echo "Verwendung: $0 [--profile local|server] [--domain NAME] [--https|--no-https] [--webrtc public|local] [--firewall configure|off]" >&2
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

sudo install -d -m 0755 "${PROFILE_DIR}"
printf '%s\n' "${PROFILE}" | sudo tee "${PROFILE_FILE}" >/dev/null
sudo chmod 0644 "${PROFILE_FILE}"

echo
echo "========================================"
echo " Open BOS Stream Installer"
echo "========================================"
echo
echo "Profil: ${PROFILE}"
echo

echo "[1/7] Systemabhängigkeiten"
"${SCRIPT_DIR}/install-dependencies.sh"

echo
echo "[2/7] Deployment"
"${SCRIPT_DIR}/deploy.sh"

echo
echo "[3/7] Deployment-Information"

"${SCRIPT_DIR}/write-deployment-info.sh"

echo
echo "[4/7] Laufzeitumgebung"
"${SCRIPT_DIR}/initialize-runtime.sh"

echo
echo "[5/7] Service"
"${SCRIPT_DIR}/install-service.sh"

echo
echo "[6/7] Serverzugriff"
if [ "${PROFILE}" = "server" ]; then
    "${SCRIPT_DIR}/configure-server-access.sh" "${SERVER_ARGS[@]}"
else
    echo "Lokales Profil: Serverzugriff übersprungen."
fi

echo
echo "[7/7] Installation prüfen"
"${SCRIPT_DIR}/verify-installation.sh"

echo
echo "========================================"
echo " Open BOS Stream erfolgreich installiert"
echo "========================================"

#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

SKIP_GIT=false
PROFILE_OVERRIDE=""
SERVER_ARGS=()

while [ "$#" -gt 0 ]; do
    case "$1" in
        --skip-git) SKIP_GIT=true; shift ;;
        --profile)
            PROFILE_OVERRIDE="${2:-}"
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
            echo "Verwendung: $0 [--skip-git] [--profile local|server] [Serveroptionen]" >&2
            exit 2
            ;;
    esac
done
if [ -n "${PROFILE_OVERRIDE}" ]; then
    validate_installation_profile "${PROFILE_OVERRIDE}"
    export OPEN_BOS_PROFILE="${PROFILE_OVERRIDE}"
    sudo install -d -m 0755 "${PROFILE_DIR}"
    printf '%s\n' "${PROFILE_OVERRIDE}" |
        sudo tee "${PROFILE_FILE}" >/dev/null
    sudo chmod 0644 "${PROFILE_FILE}"
fi

echo
echo "========================================"
echo " Open BOS Stream Update"
echo "========================================"
echo

if [ "${SKIP_GIT}" = true ]; then

    echo "[1/8] Git-Aktualisierung übersprungen."

elif git -C "${PROJECT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then

    echo "[1/8] Aktualisiere Git-Repository ..."

    if [ "$(id -u)" -eq 0 ]; then
        PROJECT_OWNER="$(
            stat -c "%U" "${PROJECT_DIR}"
        )"

        if [ "${PROJECT_OWNER}" = "root" ]; then
            echo "Repository gehört root; Git wird als root ausgeführt."
            git -C "${PROJECT_DIR}" pull --ff-only
        else
            echo "Git wird als Repository-Besitzer ${PROJECT_OWNER} ausgeführt."
            sudo -u "${PROJECT_OWNER}" \
                -H \
                git -C "${PROJECT_DIR}" pull --ff-only
        fi
    else
        git -C "${PROJECT_DIR}" pull --ff-only
    fi

else

    echo "Git-Repository nicht erkannt."
    echo "Überspringe 'git pull'."

fi

echo
echo "[2/8] Systemabhängigkeiten ..."
"${SCRIPT_DIR}/install-dependencies.sh"

echo
echo "[3/8] Deployment ..."
"${SCRIPT_DIR}/deploy.sh"

echo
echo "[4/8] Deployment-Information ..."
"${SCRIPT_DIR}/write-deployment-info.sh"

echo
echo "[5/8] Laufzeitumgebung ..."
"${SCRIPT_DIR}/initialize-runtime.sh"

echo
echo "[6/8] Service aktualisieren ..."
"${SCRIPT_DIR}/install-service.sh"

echo
echo "[7/8] Serverzugriff aktualisieren ..."
if [ "$(installation_profile)" = "server" ]; then
    "${SCRIPT_DIR}/configure-server-access.sh" \
        --non-interactive \
        "${SERVER_ARGS[@]}"
else
    echo "Lokales Profil: Serverzugriff übersprungen."
fi

echo
echo "[8/8] Installation prüfen ..."
"${SCRIPT_DIR}/verify-installation.sh"

echo
echo "========================================"
echo " Update erfolgreich abgeschlossen"
echo "========================================"

#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

SKIP_GIT=false
PROFILE_OVERRIDE=""
SERVER_ARGS=()
MEDIAMTX_MODE="auto"
MEDIAMTX_VERSION=""
MEDIAMTX_ARCHIVE=""

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
        *)
            echo "Verwendung: $0 [--skip-git] [--profile local|server] [--install-mediamtx|--no-install-mediamtx] [--mediamtx-version VERSION] [--mediamtx-archive DATEI] [Serveroptionen]" >&2
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

    echo "[1/9] Git-Aktualisierung übersprungen."

elif git -C "${PROJECT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then

    echo "[1/9] Aktualisiere Git-Repository ..."

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
echo "[2/9] Systemabhängigkeiten ..."
"${SCRIPT_DIR}/install-dependencies.sh"

echo
echo "[3/9] MediaMTX ..."
MEDIAMTX_ARGS=(--mode "${MEDIAMTX_MODE}" --non-interactive)
if [ -n "${MEDIAMTX_VERSION}" ]; then
    MEDIAMTX_ARGS+=(--version "${MEDIAMTX_VERSION}")
fi
if [ -n "${MEDIAMTX_ARCHIVE}" ]; then
    MEDIAMTX_ARGS+=(--archive "${MEDIAMTX_ARCHIVE}")
fi
"${SCRIPT_DIR}/install-mediamtx.sh" "${MEDIAMTX_ARGS[@]}"

echo
echo "[4/9] Deployment ..."
"${SCRIPT_DIR}/deploy.sh"

echo
echo "[5/9] Deployment-Information ..."
"${SCRIPT_DIR}/write-deployment-info.sh"

echo
echo "[6/9] Laufzeitumgebung ..."
"${SCRIPT_DIR}/initialize-runtime.sh"

echo
echo "[7/9] Service aktualisieren ..."
"${SCRIPT_DIR}/install-service.sh"

echo
echo "[8/9] Serverzugriff aktualisieren ..."
if [ "$(installation_profile)" = "server" ]; then
    "${SCRIPT_DIR}/configure-server-access.sh" \
        --non-interactive \
        "${SERVER_ARGS[@]}"
else
    echo "Lokales Profil: Serverzugriff übersprungen."
fi

echo
echo "[9/9] Installation prüfen ..."
"${SCRIPT_DIR}/verify-installation.sh"

echo
echo "========================================"
echo " Update erfolgreich abgeschlossen"
echo "========================================"

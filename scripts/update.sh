#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

SKIP_GIT=false

if [ "${1:-}" = "--skip-git" ]; then
    SKIP_GIT=true
elif [ "$#" -gt 0 ]; then
    echo "Verwendung: $0 [--skip-git]" >&2
    exit 2
fi

echo
echo "========================================"
echo " Open BOS Stream Update"
echo "========================================"
echo

if [ "${SKIP_GIT}" = true ]; then

    echo "[1/7] Git-Aktualisierung übersprungen."

elif git -C "${PROJECT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then

    echo "[1/7] Aktualisiere Git-Repository ..."

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
echo "[2/7] Systemabhängigkeiten ..."
"${SCRIPT_DIR}/install-dependencies.sh"

echo
echo "[3/7] Deployment ..."
"${SCRIPT_DIR}/deploy.sh"

echo
echo "[4/7] Deployment-Information ..."
"${SCRIPT_DIR}/write-deployment-info.sh"

echo
echo "[5/7] Laufzeitumgebung ..."
"${SCRIPT_DIR}/initialize-runtime.sh"

echo
echo "[6/7] Service aktualisieren ..."
"${SCRIPT_DIR}/install-service.sh"

echo
echo "[7/7] Installation prüfen ..."
"${SCRIPT_DIR}/verify-installation.sh"

echo
echo "========================================"
echo " Update erfolgreich abgeschlossen"
echo "========================================"

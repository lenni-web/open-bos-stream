#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

echo
echo "========================================"
echo " Open BOS Stream Update"
echo "========================================"
echo

if git -C "${PROJECT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then

    echo "[1/6] Aktualisiere Git-Repository ..."
    git -C "${PROJECT_DIR}" pull --ff-only

else

    echo "Git-Repository nicht erkannt."
    echo "Überspringe 'git pull'."

fi

echo
echo "[2/6] Deployment ..."
"${SCRIPT_DIR}/deploy.sh"

echo
echo "[3/6] Deployment-Information ..."
"${SCRIPT_DIR}/write-deployment-info.sh"

echo
echo "[4/6] Laufzeitumgebung ..."
"${SCRIPT_DIR}/initialize-runtime.sh"

echo
echo "[5/6] Service aktualisieren ..."
"${SCRIPT_DIR}/install-service.sh"

echo
echo "[6/6] Installation prüfen ..."
"${SCRIPT_DIR}/verify-installation.sh"

echo
echo "========================================"
echo " Update erfolgreich abgeschlossen"
echo "========================================"
#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

echo
echo "========================================"
echo " Open BOS Stream Installer"
echo "========================================"
echo

echo "[1/5] Systemabhängigkeiten"
"${SCRIPT_DIR}/install-dependencies.sh"

echo
echo "[2/5] Deployment"
"${SCRIPT_DIR}/deploy.sh"

echo
echo "[3/6] Deployment-Information"

"${SCRIPT_DIR}/write-deployment-info.sh"

echo
echo "[4/6] Laufzeitumgebung"
"${SCRIPT_DIR}/initialize-runtime.sh"

echo
echo "[5/6] Service"
"${SCRIPT_DIR}/install-service.sh"

echo
echo "[6/6] Installation prüfen"
"${SCRIPT_DIR}/verify-installation.sh"

echo
echo "========================================"
echo " Open BOS Stream erfolgreich installiert"
echo "========================================"
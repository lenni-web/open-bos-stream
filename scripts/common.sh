#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
    pwd
)"

PROJECT_DIR="$(
    cd "${SCRIPT_DIR}/.." &&
    pwd
)"

TARGET_DIR="/opt/open-bos-stream"

SERVICE_NAME="open-bos-stream.service"

SERVICE_FILE="${SCRIPT_DIR}/open-bos-stream.service"

if [ ! -f "${SERVICE_FILE}" ]; then
    fail "Service-Datei nicht gefunden: ${SERVICE_FILE}"
fi

SERVICE_USER="$(
    awk -F= '/^User=/{print $2}' "${SERVICE_FILE}"
)"

SERVICE_GROUP="$(
    awk -F= '/^Group=/{print $2}' "${SERVICE_FILE}"
)"

VENV_DIR="${TARGET_DIR}/.venv"

print_header() {

    echo
    echo "========================================"
    echo " $1"
    echo "========================================"
    echo
}

fail() {

    echo
    echo "FEHLER:"
    echo "  $1"
    exit 1
}
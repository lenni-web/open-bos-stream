#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

echo
echo "========================================"
echo " Open BOS Stream Deployment"
echo "========================================"
echo

echo "Quelle:"
echo "  ${PROJECT_DIR}"

echo "Ziel:"
echo "  ${TARGET_DIR}"
echo

sudo mkdir -p "${TARGET_DIR}"

sudo rsync \
    --archive \
    --delete \
    --human-readable \
    \
    --exclude ".git/" \
    --exclude ".github/" \
    --exclude ".venv/" \
    --exclude "__pycache__/" \
    --exclude "*.pyc" \
    \
    --exclude "config/" \
    --exclude "recordings/" \
    --exclude "snapshots/" \
    --exclude "mapdata/" \
    \
    "${PROJECT_DIR}/" \
    "${TARGET_DIR}/"

echo
echo "Deployment erfolgreich abgeschlossen."
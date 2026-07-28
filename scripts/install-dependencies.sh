#!/bin/bash

set -euo pipefail

echo
echo "Prüfe Systemabhängigkeiten ..."
echo

if ! command -v apt-get >/dev/null 2>&1; then
    echo "FEHLER: Dieser Installer unterstützt derzeit nur Debian/Ubuntu/Raspberry Pi OS."
    exit 1
fi

PACKAGES=(
    python3
    python3-venv
    python3-pip
    ffmpeg
    curl
    git
    chromium
)

MISSING_PACKAGES=()

for package in "${PACKAGES[@]}"; do
    if ! dpkg-query \
        -W \
        -f='${Status}' \
        "${package}" \
        2>/dev/null \
        | grep -q "install ok installed"
    then
        MISSING_PACKAGES+=("${package}")
    fi
done

if [ "${#MISSING_PACKAGES[@]}" -eq 0 ]; then
    echo "Alle benötigten Systempakete sind bereits installiert."
    exit 0
fi

echo "Folgende Pakete werden installiert:"
printf '  - %s\n' "${MISSING_PACKAGES[@]}"

echo
sudo apt-get update

sudo apt-get install \
    --yes \
    "${MISSING_PACKAGES[@]}"

echo
echo "Systemabhängigkeiten wurden installiert."

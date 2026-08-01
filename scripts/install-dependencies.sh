#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"
PROFILE="$(installation_profile)"
validate_installation_profile "${PROFILE}"

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
    sudo
    tar
)

if [ "${PROFILE}" = "local" ]; then
    PACKAGES+=(
        dbus-daemon
        labwc
        seatd
    )
fi

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

if [ "${PROFILE}" = "server" ]; then
    echo "Server-Profil: Chromium und Wayland-Komponenten werden ausgelassen."
elif command -v chromium >/dev/null 2>&1 ||
    command -v chromium-browser >/dev/null 2>&1
then
    echo "Chromium ist bereits installiert."
elif apt-cache show chromium >/dev/null 2>&1; then
    MISSING_PACKAGES+=("chromium")
elif apt-cache show chromium-browser >/dev/null 2>&1; then
    MISSING_PACKAGES+=("chromium-browser")
else
    echo "FEHLER: Kein Chromium-Paket in den Paketquellen gefunden."
    exit 1
fi

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

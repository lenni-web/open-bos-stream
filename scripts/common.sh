#!/bin/bash

set -euo pipefail

fail() {
    echo
    echo "FEHLER:"
    echo "  $1"
    exit 1
}

# Auf minimalen Debian-Systemen ist sudo bei einem direkten Root-Aufruf nicht
# zwingend installiert. Bis install-dependencies.sh es ergänzt, führt dieser
# kleine kompatible Wrapper privilegierte Befehle direkt und Benutzerwechsel
# über runuser aus.
if [ "$(id -u)" -eq 0 ] && ! command -v sudo >/dev/null 2>&1; then
    sudo() {
        local target_user=""
        while [ "$#" -gt 0 ]; do
            case "$1" in
                -H) shift ;;
                -u)
                    target_user="${2:-}"
                    shift 2
                    ;;
                --)
                    shift
                    break
                    ;;
                -*) fail "Nicht unterstützte sudo-Option im Root-Modus: $1" ;;
                *) break ;;
            esac
        done
        if [ -n "${target_user}" ]; then
            runuser -u "${target_user}" -- "$@"
        else
            "$@"
        fi
    }
elif [ "$(id -u)" -ne 0 ] && ! command -v sudo >/dev/null 2>&1; then
    fail "sudo fehlt. Bitte als root installieren oder den Installer direkt als root starten."
fi

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

VENV_DIR="${TARGET_DIR}/.venv"

PROFILE_DIR="/etc/open-bos-stream"
PROFILE_FILE="${PROFILE_DIR}/profile"
SERVER_CONFIG_FILE="${PROFILE_DIR}/server.env"
INSTALL_CONFIG_FILE="${PROFILE_DIR}/install.env"

read_install_setting() {
    local key="$1"
    local fallback="$2"
    local value=""
    if [ -f "${INSTALL_CONFIG_FILE}" ]; then
        value="$(
            awk -F= -v key="${key}" \
                '$1 == key {sub(/^[^=]*=/, ""); print; exit}' \
                "${INSTALL_CONFIG_FILE}"
        )"
    fi
    printf '%s\n' "${value:-${fallback}}"
}

DEFAULT_SERVICE_USER="$(
    awk -F= '/^User=/{print $2; exit}' "${SERVICE_FILE}"
)"
DEFAULT_SERVICE_GROUP="$(
    awk -F= '/^Group=/{print $2; exit}' "${SERVICE_FILE}"
)"
SERVICE_USER="${OPEN_BOS_SERVICE_USER:-$(
    read_install_setting SERVICE_USER "${DEFAULT_SERVICE_USER:-streampi}"
)}"
SERVICE_GROUP="${OPEN_BOS_SERVICE_GROUP:-$(
    read_install_setting SERVICE_GROUP "${DEFAULT_SERVICE_GROUP:-video}"
)}"

validate_service_identity() {
    if ! [[ "$1" =~ ^[a-z_][a-z0-9_-]*\$?$ ]]; then
        fail "Ungültiger Dienstbenutzer: $1"
    fi
    if ! [[ "$2" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
        fail "Ungültige Dienstgruppe: $2"
    fi
}

installation_profile() {
    if [ -n "${OPEN_BOS_PROFILE:-}" ]; then
        printf '%s\n' "${OPEN_BOS_PROFILE}"
    elif [ -f "${PROFILE_FILE}" ]; then
        tr -d '[:space:]' < "${PROFILE_FILE}"
    else
        printf '%s\n' "local"
    fi
}

validate_installation_profile() {
    case "$1" in
        local|server) ;;
        *) fail "Unbekanntes Installationsprofil: $1" ;;
    esac
}

print_header() {

    echo
    echo "========================================"
    echo " $1"
    echo "========================================"
    echo
}

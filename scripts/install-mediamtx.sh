#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

MEDIAMTX_VERSION="${OPEN_BOS_MEDIAMTX_VERSION:-1.19.3}"
MODE="auto"
ARCHIVE=""
INTERACTIVE=false
TARGET_BINARY="/usr/local/bin/mediamtx"
TEMPORARY=""

cleanup() {
    if [ -n "${TEMPORARY}" ] && [ -d "${TEMPORARY}" ]; then
        rm -rf -- "${TEMPORARY}"
    fi
}
trap cleanup EXIT

while [ "$#" -gt 0 ]; do
    case "$1" in
        --mode)
            MODE="${2:-}"
            shift 2
            ;;
        --version)
            MEDIAMTX_VERSION="${2:-}"
            shift 2
            ;;
        --archive)
            ARCHIVE="${2:-}"
            MODE="install"
            shift 2
            ;;
        --interactive)
            INTERACTIVE=true
            shift
            ;;
        --non-interactive)
            INTERACTIVE=false
            shift
            ;;
        *)
            echo "Verwendung: $0 [--mode auto|install|external] [--version VERSION] [--archive DATEI] [--interactive|--non-interactive]" >&2
            exit 2
            ;;
    esac
done

case "${MODE}" in
    auto|install|external) ;;
    *) fail "Ungültiger MediaMTX-Modus: ${MODE}" ;;
esac

if ! [[ "${MEDIAMTX_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    fail "Ungültige MediaMTX-Version: ${MEDIAMTX_VERSION}"
fi

find_existing_mediamtx() {
    local candidate=""
    local service_home=""
    if [ -x "${TARGET_BINARY}" ]; then
        printf '%s\n' "${TARGET_BINARY}"
        return
    fi
    if command -v mediamtx >/dev/null 2>&1; then
        candidate="$(command -v mediamtx)"
        if [ -x "${candidate}" ]; then
            printf '%s\n' "${candidate}"
            return
        fi
    fi
    service_home="$(
        getent passwd "${SERVICE_USER}" 2>/dev/null |
            awk -F: '{print $6; exit}'
    )"
    for candidate in \
        /home/streampi/mediamtx \
        "${service_home:-/home/${SERVICE_USER}}/mediamtx"
    do
        if [ -x "${candidate}" ]; then
            printf '%s\n' "${candidate}"
            return
        fi
    done
    return 0
}

atomic_install() {
    local source_binary="$1"
    local staged_binary="${TARGET_BINARY}.new"
    sudo install -o root -g root -m 0755 \
        "${source_binary}" "${staged_binary}"
    sudo mv -f "${staged_binary}" "${TARGET_BINARY}"
}

install_existing_binary() {
    local source_binary="$1"
    if [ "${source_binary}" != "${TARGET_BINARY}" ]; then
        echo "Übernehme vorhandenes MediaMTX aus ${source_binary} ..."
        atomic_install "${source_binary}"
    fi
}

download_and_install() {
    local machine architecture asset base_url checksum expected actual
    machine="$(uname -m)"
    case "${machine}" in
        x86_64|amd64) architecture="amd64" ;;
        aarch64|arm64) architecture="arm64" ;;
        armv7l|armv7) architecture="armv7" ;;
        armv6l|armv6) architecture="armv6" ;;
        *) fail "MediaMTX wird für die Architektur '${machine}' nicht automatisch installiert." ;;
    esac

    asset="mediamtx_v${MEDIAMTX_VERSION}_linux_${architecture}.tar.gz"
    base_url="https://github.com/bluenviron/mediamtx/releases/download/v${MEDIAMTX_VERSION}"
    TEMPORARY="$(mktemp -d)"

    if [ -n "${ARCHIVE}" ]; then
        if [ ! -f "${ARCHIVE}" ]; then
            fail "MediaMTX-Archiv nicht gefunden: ${ARCHIVE}"
        fi
        cp "${ARCHIVE}" "${TEMPORARY}/${asset}"
    else
        echo "Lade MediaMTX v${MEDIAMTX_VERSION} für ${architecture} ..."
        curl --fail --location --show-error --silent \
            --output "${TEMPORARY}/${asset}" \
            "${base_url}/${asset}"
    fi

    checksum="${TEMPORARY}/checksums.sha256"
    if [ -n "${ARCHIVE}" ] && [ -f "${ARCHIVE}.sha256" ]; then
        cp "${ARCHIVE}.sha256" "${checksum}"
        expected="$(awk 'NF {print $1; exit}' "${checksum}")"
    else
        curl --fail --location --show-error --silent \
            --output "${checksum}" \
            "${base_url}/checksums.sha256"
        expected="$(
            awk -v asset="${asset}" \
                '$2 == asset || $2 == "*" asset {print $1; exit}' \
                "${checksum}"
        )"
    fi
    if [ -z "${expected}" ]; then
        fail "Keine offizielle Prüfsumme für ${asset} gefunden."
    fi
    actual="$(sha256sum "${TEMPORARY}/${asset}" | awk '{print $1}')"
    if [ "${actual}" != "${expected}" ]; then
        fail "SHA256-Prüfung des MediaMTX-Archivs fehlgeschlagen."
    fi

    tar -xzf "${TEMPORARY}/${asset}" -C "${TEMPORARY}" mediamtx
    atomic_install "${TEMPORARY}/mediamtx"
    cleanup
    TEMPORARY=""
}

existing="$(find_existing_mediamtx)"
if [ "${MODE}" = "install" ]; then
    download_and_install
elif [ -n "${existing}" ]; then
    install_existing_binary "${existing}"
elif [ "${MODE}" = "external" ]; then
    fail "MediaMTX fehlt. Ohne automatische Installation muss es im PATH, unter /home/streampi/mediamtx oder im Home des Dienstbenutzers vorhanden sein."
else
    if [ "${INTERACTIVE}" = true ] && [ -t 0 ]; then
        read -r -p "MediaMTX v${MEDIAMTX_VERSION} automatisch installieren? [J/n]: " answer
        case "${answer:-j}" in
            j|J|ja|JA|yes|YES) ;;
            *) fail "Installation ohne MediaMTX abgebrochen." ;;
        esac
    fi
    download_and_install
fi

if [ ! -x "${TARGET_BINARY}" ]; then
    fail "MediaMTX wurde nicht unter ${TARGET_BINARY} installiert."
fi

echo "MediaMTX bereit: $(${TARGET_BINARY} --version 2>&1 | head -n 1)"

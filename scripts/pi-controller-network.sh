#!/bin/bash
#
# Raspberry Pi vor Ort: Netzwerkanschluss für einen Drohnen-Controller.
#
# Der Pi holt den RTSP-Stream des Controllers über eine eigene
# Netzwerkschnittstelle ab (meist ein USB-Ethernet-Adapter) und sendet ihn
# per SRT über Mobilfunk an den Server. Damit der Mobilfunk die
# Standardroute bleibt, bekommt die Controller-Verbindung nie eine
# Standardroute (ipv4.never-default).
#
# Modi:
#   dhcp   Der Controller vergibt die Adresse (z. B. Parrot SkyController).
#   share  Der Pi vergibt die Adresse (z. B. Skydio Enterprise Controller).
#          Der Controller erhält eine Adresse aus 10.42.0.0/24; der Pi ist
#          10.42.0.1. NetworkManager teilt dabei auch den Mobilfunk-
#          Zugang des Pi mit dem Controller (z. B. für Kartendaten der App).
#   status Verbindungen, Routen und vergebene Adressen anzeigen.
#   remove Controller-Verbindung wieder entfernen.
#
# Voraussetzung: Raspberry Pi OS ab Bookworm (NetworkManager).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

CONNECTION="open-bos-controller"
INTERFACE="eth0"
MODE=""

usage() {
    cat <<'EOF'
Verwendung:
  scripts/pi-controller-network.sh dhcp   [--interface eth0]
  scripts/pi-controller-network.sh share  [--interface eth0]
  scripts/pi-controller-network.sh status
  scripts/pi-controller-network.sh remove

dhcp   Controller vergibt die Adresse (Parrot SkyController).
share  Pi vergibt die Adresse 10.42.0.x (Skydio, andere Controller).
EOF
}

if [ "$#" -lt 1 ]; then
    usage
    exit 1
fi

MODE="$1"
shift

while [ "$#" -gt 0 ]; do
    case "$1" in
        --interface)
            INTERFACE="${2:-}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "Unbekannte Option: $1"
            ;;
    esac
done

if [ "$(installation_profile)" = "server" ]; then
    fail "Dieses Skript ist für den Raspberry Pi vor Ort (lokales Profil)."
fi

if ! command -v nmcli >/dev/null 2>&1; then
    fail "NetworkManager (nmcli) fehlt. Benötigt wird Raspberry Pi OS ab Bookworm."
fi

connection_exists() {
    # Ausgabe erst einsammeln: grep -q könnte nmcli sonst per SIGPIPE
    # beenden, was mit pipefail als „nicht gefunden“ gälte.
    local names
    names="$(nmcli -g NAME connection show)"
    grep -qx "${CONNECTION}" <<<"${names}"
}

show_status() {
    echo "Verbindungen:"
    nmcli -f NAME,DEVICE,TYPE,STATE connection show
    echo
    echo "Standardroute (sollte über Mobilfunk laufen):"
    ip route show default || true
    echo
    if connection_exists; then
        echo "Controller-Verbindung ${CONNECTION}:"
        nmcli -f GENERAL.DEVICES,GENERAL.STATE,IP4.ADDRESS,IP4.GATEWAY \
            connection show "${CONNECTION}" || true
    else
        echo "Controller-Verbindung ${CONNECTION} ist nicht eingerichtet."
    fi
    local leases
    for leases in /var/lib/NetworkManager/dnsmasq-*.leases; do
        [ -f "${leases}" ] || continue
        echo
        echo "Vom Pi vergebene Adressen (${leases##*/}):"
        awk '{print "  " $3 "  " $4 "  " $2}' "${leases}"
    done
}

remove_connection() {
    if connection_exists; then
        sudo nmcli connection delete "${CONNECTION}"
        echo "Controller-Verbindung entfernt."
    else
        echo "Keine Controller-Verbindung eingerichtet."
    fi
}

configure() {
    local method="$1"

    if ! ip link show "${INTERFACE}" >/dev/null 2>&1; then
        fail "Netzwerkschnittstelle ${INTERFACE} nicht gefunden. Mit 'ip link' prüfen und --interface angeben."
    fi

    remove_connection >/dev/null

    sudo nmcli connection add \
        type ethernet \
        ifname "${INTERFACE}" \
        con-name "${CONNECTION}" \
        connection.autoconnect yes \
        ipv4.method "${method}" \
        ipv4.never-default yes \
        ipv6.method disabled

    sudo nmcli connection up "${CONNECTION}" || \
        echo "Hinweis: Verbindung wird aktiv, sobald der Controller angeschlossen ist."

    echo
    echo "Controller-Verbindung auf ${INTERFACE} eingerichtet (${MODE})."
    if [ "${method}" = "shared" ]; then
        echo "Der Pi ist 10.42.0.1; der Controller erhält eine Adresse aus 10.42.0.0/24."
        echo "Welche Adresse vergeben wurde, zeigt: scripts/pi-controller-network.sh status"
    fi
    echo "Die Standardroute bleibt beim Mobilfunk."
}

case "${MODE}" in
    dhcp)
        configure auto
        ;;
    share)
        configure shared
        ;;
    status)
        show_status
        ;;
    remove)
        remove_connection
        ;;
    *)
        usage
        exit 1
        ;;
esac

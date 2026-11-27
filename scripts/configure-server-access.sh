#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"
source "$(cd "$(dirname "$0")" && pwd)/server-access-lib.sh"

if [ "$(installation_profile)" != "server" ]; then
    fail "Öffentlicher Serverzugriff ist nur im Server-Profil verfügbar."
fi

DOMAIN=""
HTTPS_MODE=""
WEBRTC_MODE=""
WEBRTC_EXPLICIT=false
FIREWALL_MODE=""
INTERACTIVE=false
# Weitere Domains, die per Weiterleitung auf die Hauptdomain zeigen.
ALIAS_ADD=""
ALIAS_REMOVE=""
ALIAS_CLEAR=""

normalize_domain() {
    local value="$1"
    value="${value#http://}"
    value="${value#https://}"
    value="${value%/}"
    printf '%s\n' "${value}" | tr '[:upper:]' '[:lower:]'
}

read_setting() {
    local key="$1"
    local fallback="$2"
    if [ ! -f "${SERVER_CONFIG_FILE}" ]; then
        printf '%s\n' "${fallback}"
        return
    fi
    local value
    value="$(
        awk -F= -v key="${key}" \
            '$1 == key {sub(/^[^=]*=/, ""); print; exit}' \
            "${SERVER_CONFIG_FILE}"
    )"
    printf '%s\n' "${value:-${fallback}}"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --domain)
            DOMAIN="${2:-}"
            shift 2
            ;;
        --https)
            HTTPS_MODE="yes"
            shift
            ;;
        --no-https)
            HTTPS_MODE="no"
            shift
            ;;
        --webrtc)
            WEBRTC_MODE="${2:-}"
            WEBRTC_EXPLICIT=true
            shift 2
            ;;
        --firewall)
            FIREWALL_MODE="${2:-}"
            shift 2
            ;;
        --alias-domain)
            ALIAS_ADD="${ALIAS_ADD} ${2:-}"
            shift 2
            ;;
        --remove-alias-domain)
            ALIAS_REMOVE="${ALIAS_REMOVE} ${2:-}"
            shift 2
            ;;
        --clear-alias-domains)
            ALIAS_CLEAR="clear"
            shift
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
            echo "Verwendung: $0 [--domain NAME] [--alias-domain NAME ...] [--remove-alias-domain NAME] [--clear-alias-domains] [--https|--no-https] [--webrtc public|local] [--firewall configure|off]" >&2
            exit 2
            ;;
    esac
done

DOMAIN="${DOMAIN:-$(read_setting PUBLIC_DOMAIN "")}"
HTTPS_MODE="${HTTPS_MODE:-$(read_setting HTTPS_ENABLED "no")}"
WEBRTC_MODE="${WEBRTC_MODE:-$(read_setting WEBRTC_MODE "local")}"
FIREWALL_MODE="${FIREWALL_MODE:-$(read_setting FIREWALL_MODE "off")}"
PREVIOUS_HTTPS="$(read_setting HTTPS_ENABLED "no")"
ALIAS_CURRENT="$(read_setting ALIAS_DOMAINS "")"

if [ ! -f "${SERVER_CONFIG_FILE}" ] && [ -t 0 ]; then
    INTERACTIVE=true
fi

if [ "${INTERACTIVE}" = true ]; then
    read -r -p "Öffentliche Domain, z. B. ffw-stream.de (leer = kein HTTPS) [${DOMAIN}]: " answer
    DOMAIN="${answer:-${DOMAIN}}"

    if [ -n "${DOMAIN}" ]; then
        read -r -p "HTTPS mit Caddy einrichten? [J/n]: " answer
        case "${answer:-j}" in
            j|J|ja|JA|yes|YES) HTTPS_MODE="yes" ;;
            *) HTTPS_MODE="no" ;;
        esac

        if [ "${HTTPS_MODE}" = "yes" ]; then
            read -r -p "Weitere Domains, die auf ${DOMAIN} weiterleiten (kommagetrennt, - = keine) [${ALIAS_CURRENT}]: " answer
            case "${answer}" in
                "") ;;
                -) ALIAS_CLEAR="clear" ;;
                *) ALIAS_CLEAR="clear"; ALIAS_ADD="${answer}" ;;
            esac

            read -r -p "WebRTC öffentlich über diese Domain bereitstellen? [J/n]: " answer
            case "${answer:-j}" in
                j|J|ja|JA|yes|YES) WEBRTC_MODE="public" ;;
                *) WEBRTC_MODE="local" ;;
            esac
        else
            WEBRTC_MODE="local"
        fi
    fi

    echo
    echo "Die optionale Firewall lässt SSH, HTTP, HTTPS, RTMP, SRT und WebRTC zu."
    echo "RTMP (TCP 1935) und SRT (UDP 8890) sind unverschlüsselt, Sender benötigen aber einen Token."
    read -r -p "UFW-Regeln jetzt konfigurieren? [j/N]: " answer
    case "${answer:-n}" in
        j|J|ja|JA|yes|YES) FIREWALL_MODE="configure" ;;
        *) FIREWALL_MODE="off" ;;
    esac
fi

# Bedienfreundlich sowohl einen Hostnamen als auch eine kopierte Webadresse
# akzeptieren. Pfade, Ports und Zugangsdaten bleiben bewusst unzulässig.
DOMAIN="$(normalize_domain "${DOMAIN}")"
ALIAS_DOMAINS="$(
    access_alias_domains "${DOMAIN}" "${ALIAS_CURRENT}" \
        "${ALIAS_ADD}" "${ALIAS_REMOVE}" "${ALIAS_CLEAR}"
)" || fail "Weiterleitungs-Domains müssen gültige Domains ohne Pfad oder Port sein (z. B. drohnen.beispiel.de)."
if [ -n "${ALIAS_DOMAINS}" ] && [ "${HTTPS_MODE}" != "yes" ]; then
    echo "HINWEIS: Weiterleitungs-Domains (${ALIAS_DOMAINS}) wirken erst mit HTTPS über Caddy."
fi

case "${HTTPS_MODE}" in yes|no) ;; *) fail "HTTPS muss yes oder no sein." ;; esac
case "${WEBRTC_MODE}" in public|local) ;; *) fail "WebRTC muss public oder local sein." ;; esac
case "${FIREWALL_MODE}" in configure|off) ;; *) fail "Firewall muss configure oder off sein." ;; esac

if [ "${HTTPS_MODE}" = "no" ] &&
    [ "${WEBRTC_EXPLICIT}" = false ]; then
    WEBRTC_MODE="local"
fi

if [ "${WEBRTC_MODE}" = "public" ] && [ "${HTTPS_MODE}" != "yes" ]; then
    fail "Öffentliches WebRTC benötigt die HTTPS-Weiterleitung über Caddy."
fi

if [ "${HTTPS_MODE}" = "yes" ] || [ "${WEBRTC_MODE}" = "public" ]; then
    if ! [[ "${DOMAIN}" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] ||
        [[ "${DOMAIN}" != *.* ]]; then
        fail "Für HTTPS/WebRTC wird eine gültige öffentliche Domain ohne Pfad oder Port benötigt (z. B. ffw-stream.de)."
    fi
fi

sudo install -d -m 0755 "${PROFILE_DIR}"
settings_tmp="$(mktemp)"
trap 'rm -f "${settings_tmp}" "${caddy_tmp:-}" "${mediamtx_tmp:-}" "${service_override_tmp:-}"' EXIT
{
    printf 'PUBLIC_DOMAIN=%s\n' "${DOMAIN}"
    printf 'ALIAS_DOMAINS=%s\n' "${ALIAS_DOMAINS}"
    printf 'HTTPS_ENABLED=%s\n' "${HTTPS_MODE}"
    printf 'WEBRTC_MODE=%s\n' "${WEBRTC_MODE}"
    printf 'FIREWALL_MODE=%s\n' "${FIREWALL_MODE}"
} > "${settings_tmp}"
sudo install -m 0644 "${settings_tmp}" "${SERVER_CONFIG_FILE}"

if [ "${HTTPS_MODE}" = "yes" ]; then
    if ! getent ahosts "${DOMAIN}" >/dev/null 2>&1; then
        echo "WARNUNG: ${DOMAIN} kann derzeit nicht per DNS aufgelöst werden."
        echo "Caddy kann erst nach korrektem A-/AAAA-Eintrag ein Zertifikat beziehen."
    fi

    if ! command -v caddy >/dev/null 2>&1; then
        echo "Installiere Caddy aus den Debian-Paketquellen ..."
        sudo apt-get update
        sudo apt-get install --yes caddy
    fi

    caddy_tmp="$(mktemp)"
    sed "s/__DOMAIN__/${DOMAIN}/g" \
        "${SCRIPT_DIR}/Caddyfile.server" > "${caddy_tmp}"
    # Weitere Domains erhalten ein eigenes Zertifikat und leiten dauerhaft
    # auf die Hauptdomain um (eine Anmeldung, eine App, ein Push-Ziel).
    access_caddy_redirect_block "${DOMAIN}" "${ALIAS_DOMAINS}" >> "${caddy_tmp}"
    for alias_domain in ${ALIAS_DOMAINS//,/ }; do
        if ! getent ahosts "${alias_domain}" >/dev/null 2>&1; then
            echo "WARNUNG: ${alias_domain} kann derzeit nicht per DNS aufgelöst werden."
        fi
    done
    sudo install -d -m 0755 /etc/caddy
    sudo install -m 0644 "${caddy_tmp}" /etc/caddy/Caddyfile
    sudo caddy validate --config /etc/caddy/Caddyfile
    sudo systemctl enable caddy.service
    sudo systemctl restart caddy.service
    echo "HTTPS-Proxy eingerichtet: https://${DOMAIN}"
    if [ -n "${ALIAS_DOMAINS}" ]; then
        echo "Weiterleitung auf https://${DOMAIN}: ${ALIAS_DOMAINS//,/, }"
    fi

    service_override_tmp="$(mktemp)"
    {
        echo "[Service]"
        echo "ExecStart="
        # Nur Caddy auf 127.0.0.1 darf X-Forwarded-For/-Proto setzen.
        echo "ExecStart=/opt/open-bos-stream/.venv/bin/python -m uvicorn open_bos_stream.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1"
    } > "${service_override_tmp}"
    sudo install -d -m 0755 \
        /etc/systemd/system/open-bos-stream.service.d
    sudo install -m 0644 \
        "${service_override_tmp}" \
        /etc/systemd/system/open-bos-stream.service.d/server-bind.conf
else
    echo "HTTPS bleibt deaktiviert."
    echo
    echo "WARNUNG: Ohne HTTPS werden Passwörter, Sitzungen und Livebilder"
    echo "unverschlüsselt übertragen. Für einen über das Internet erreichbaren"
    echo "Server bitte HTTPS aktivieren (--domain NAME --https)."
    echo
    if [ "${PREVIOUS_HTTPS}" = "yes" ] &&
        systemctl cat caddy.service >/dev/null 2>&1; then
        sudo systemctl disable --now caddy.service
    fi
    sudo rm -f \
        /etc/systemd/system/open-bos-stream.service.d/server-bind.conf
fi

mediamtx_tmp="$(mktemp)"
cp "${PROJECT_DIR}/config/mediamtx.server.yml" "${mediamtx_tmp}"
if [ "${HTTPS_MODE}" = "yes" ]; then
    {
        echo 'hlsAddress: 127.0.0.1:8888'
        echo 'webrtcAddress: 127.0.0.1:8889'
    } >> "${mediamtx_tmp}"
fi
if [ "${WEBRTC_MODE}" = "public" ]; then
    {
        echo
        printf 'webrtcAdditionalHosts: [%s]\n' "${DOMAIN}"
        echo 'webrtcLocalUDPAddress: :8189'
        echo 'webrtcLocalTCPAddress: :8189'
    } >> "${mediamtx_tmp}"
fi
sudo install -m 0644 "${mediamtx_tmp}" "${PROFILE_DIR}/mediamtx.yml"
sudo systemctl daemon-reload
sudo systemctl restart open-bos-stream.service
sudo systemctl restart mediamtx.service

if [ "${FIREWALL_MODE}" = "configure" ]; then
    if ! command -v ufw >/dev/null 2>&1; then
        sudo apt-get update
        sudo apt-get install --yes ufw
    fi

    ssh_port="$(
        sudo sshd -T 2>/dev/null |
            awk '$1 == "port" {print $2; exit}'
    )"
    ssh_port="${ssh_port:-22}"

    echo "Aktiviere UFW; SSH bleibt auf TCP ${ssh_port} erreichbar."
    for rule in \
        80/tcp \
        443/tcp \
        8000/tcp \
        8888/tcp \
        8889/tcp \
        1935/tcp \
        8890/udp \
        8189/tcp \
        8189/udp
    do
        sudo ufw --force delete allow "${rule}" >/dev/null 2>&1 || true
    done
    sudo ufw allow "${ssh_port}/tcp" comment "SSH"
    if [ "${HTTPS_MODE}" = "yes" ]; then
        sudo ufw allow 80/tcp comment "HTTP / ACME"
        sudo ufw allow 443/tcp comment "HTTPS"
    else
        sudo ufw allow 8000/tcp comment "Open BOS HTTP"
        sudo ufw allow 8888/tcp comment "MediaMTX HLS"
        sudo ufw allow 8889/tcp comment "MediaMTX WHEP"
    fi
    sudo ufw allow 1935/tcp comment "RTMP Publisher Token"
    sudo ufw allow 8890/udp comment "SRT Publisher Token"
    sudo ufw allow 8189/tcp comment "MediaMTX WebRTC TCP fallback"
    sudo ufw allow 8189/udp comment "MediaMTX WebRTC"
    sudo ufw --force enable
    sudo ufw status verbose
else
    echo "Host-Firewall wurde nicht verändert."
fi

echo
echo "Serverzugriff konfiguriert."
echo "RTMP: rtmp://${DOMAIN:-SERVER-IP}:1935/<quellen-id>?token=<TOKEN>"
echo "SRT:  srt://${DOMAIN:-SERVER-IP}:8890?streamid=publish:<quellen-id>:token=<TOKEN>"

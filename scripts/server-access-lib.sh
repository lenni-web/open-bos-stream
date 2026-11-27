#!/bin/bash
# Reine Hilfsfunktionen für configure-server-access.sh: keine
# Seiteneffekte, daher auch in den Tests direkt aufrufbar.

access_normalize_domain() {
    local value="$1"
    value="${value#http://}"
    value="${value#https://}"
    value="${value%/}"
    printf '%s\n' "${value}" | tr '[:upper:]' '[:lower:]'
}

access_valid_domain() {
    [[ "$1" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] && [[ "$1" == *.* ]]
}

# Weiterleitungs-Domains zusammenstellen.
# Argumente: Hauptdomain, bisherige Liste, hinzuzufügen, zu entfernen
# (Listen jeweils komma- oder leerzeichengetrennt), "clear" = alle löschen.
# Ausgabe: bereinigte, kommagetrennte Liste ohne Hauptdomain und Dubletten.
access_alias_domains() {
    local primary current add remove clear
    primary="$(access_normalize_domain "$1")"
    current="$2"
    add="$3"
    remove="$4"
    clear="${5:-}"
    [ "${clear}" = "clear" ] && current=""

    local -a result=()
    local item normalized removed seen
    for item in ${current//,/ } ${add//,/ }; do
        normalized="$(access_normalize_domain "${item}")"
        [ -z "${normalized}" ] && continue
        [ "${normalized}" = "${primary}" ] && continue
        removed=false
        for seen in ${remove//,/ }; do
            if [ "$(access_normalize_domain "${seen}")" = "${normalized}" ]; then
                removed=true
            fi
        done
        [ "${removed}" = true ] && continue
        if ! access_valid_domain "${normalized}"; then
            echo "Ungültige Weiterleitungs-Domain: ${item}" >&2
            return 1
        fi
        for seen in "${result[@]+"${result[@]}"}"; do
            [ "${seen}" = "${normalized}" ] && continue 2
        done
        result+=("${normalized}")
    done
    local IFS=","
    printf '%s\n' "${result[*]+"${result[*]}"}"
}

# Caddy-Block: alle Weiterleitungs-Domains (mit eigenem Zertifikat) leiten
# dauerhaft auf die Hauptdomain um; Pfad und Parameter bleiben erhalten.
access_caddy_redirect_block() {
    local primary="$1"
    local aliases="$2"
    [ -z "${aliases}" ] && return 0
    printf '\n%s {\n' "${aliases//,/, }"
    printf '\tredir https://%s{uri} permanent\n' "${primary}"
    printf '}\n'
}

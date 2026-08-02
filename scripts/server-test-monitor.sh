#!/bin/bash

set -euo pipefail

DURATION=0
INTERVAL=5
OUTPUT="${PWD}/open-bos-server-test-$(date +%Y%m%d-%H%M%S)"
MONITOR_PID=""
STARTED_AT=""
FINISHED=false

usage() {
    cat <<'EOF'
Verwendung: sudo server-test-monitor.sh [Optionen]

Sammelt während eines Mehrquellentests Systemwerte und exportiert danach die
Journale von Open BOS Stream, Streamer, MediaMTX, Caddy und Kernel.

Optionen:
  --duration SEK     Laufzeit; 0 läuft bis Strg+C (Standard: 0)
  --interval SEK     Messabstand (Standard: 5)
  --output PFAD      Zielverzeichnis
  -h, --help         Hilfe anzeigen
EOF
}

fail() {
    echo "FEHLER: $*" >&2
    exit 1
}

redact_stream() {
    sed -E \
        -e 's#(://[^/@[:space:]]*:)[^@/[:space:]]+@#\1***@#g' \
        -e 's#([?&](token|passphrase|password|pass)=)[^&[:space:]]+#\1***#g'
}

finish() {
    [ "${FINISHED}" = false ] || return
    FINISHED=true
    trap - INT TERM EXIT
    [ -n "${STARTED_AT}" ] || return
    if [ -n "${MONITOR_PID}" ] && kill -0 "${MONITOR_PID}" 2>/dev/null; then
        kill -TERM "${MONITOR_PID}" 2>/dev/null || true
        wait "${MONITOR_PID}" 2>/dev/null || true
    fi
    ended_at="$(date --iso-8601=seconds)"
    printf 'started_at=%s\nended_at=%s\nduration_requested=%s\ninterval=%s\n' \
        "${STARTED_AT}" "${ended_at}" "${DURATION}" "${INTERVAL}" \
        >"${OUTPUT}/metadata.txt"
    journalctl --since "${STARTED_AT}" --until "${ended_at}" --no-pager \
        -u open-bos-stream.service \
        -u open-bos-streamer.service \
        -u mediamtx.service \
        -u caddy.service \
        2>&1 | redact_stream >"${OUTPUT}/services.log" || true
    journalctl --since "${STARTED_AT}" --until "${ended_at}" \
        -k --no-pager 2>&1 | redact_stream \
        >"${OUTPUT}/kernel.log" || true
    echo "Server-Testprotokoll abgeschlossen: ${OUTPUT}"
}
trap finish INT TERM EXIT

while [ "$#" -gt 0 ]; do
    case "$1" in
        --duration) DURATION="${2:-}"; shift 2 ;;
        --interval) INTERVAL="${2:-}"; shift 2 ;;
        --output) OUTPUT="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) fail "Unbekannte Option: $1" ;;
    esac
done

[[ "${DURATION}" =~ ^[0-9]+$ ]] || fail "Ungültige Dauer."
[[ "${INTERVAL}" =~ ^[1-9][0-9]*$ ]] || fail "Ungültiger Messabstand."
command -v journalctl >/dev/null 2>&1 || fail "journalctl fehlt."
command -v free >/dev/null 2>&1 || fail "free fehlt."
[ "$(id -u)" -eq 0 ] ||
    echo "WARNUNG: Ohne root können Journale unvollständig sein." >&2

mkdir -p "${OUTPUT}"
STARTED_AT="$(date --iso-8601=seconds)"
echo "Server-Testmonitor gestartet: ${STARTED_AT}"
echo "Ziel: ${OUTPUT}"

(
    while true; do
        echo "=== $(date --iso-8601=seconds) ==="
        uptime
        free -m
        ps -eo pid,pcpu,pmem,rss,etime,comm,args --sort=-pcpu |
            awk 'NR == 1 || /open_bos_stream|uvicorn|ffmpeg|mediamtx|caddy/' |
            redact_stream
        echo "--- Netzwerk ---"
        cat /proc/net/dev
        echo
        sleep "${INTERVAL}"
    done
) >"${OUTPUT}/system.log" 2>&1 &
MONITOR_PID="$!"

if [ "${DURATION}" -eq 0 ]; then
    wait "${MONITOR_PID}" || true
else
    remaining="${DURATION}"
    while [ "${remaining}" -gt 0 ]; do
        step=30
        [ "${remaining}" -lt "${step}" ] && step="${remaining}"
        sleep "${step}"
        remaining=$((remaining - step))
    done
fi
finish

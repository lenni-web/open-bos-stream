#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVER=""
PORT=1935
COUNT=1
FIRST_INDEX=1
DURATION=0
PATH_PREFIX="quelle-"
VIDEO="${PROJECT_DIR}/testdata/open-bos-test-720p.mp4"
TOKENS_FILE=""
LOG_DIR="${PROJECT_DIR}/test-results/$(date +%Y%m%d-%H%M%S)"
PIDS=()
SOURCE_IDS=()
FFMPEG_BIN="${FFMPEG_BIN:-ffmpeg}"
FFPROBE_BIN="${FFPROBE_BIN:-ffprobe}"

usage() {
    cat <<'EOF'
Verwendung: multi-source-test.sh --server HOST --tokens-file DATEI [Optionen]

Veröffentlicht denselben Testclip in Echtzeit auf 1, 4 oder 8 RTMP-Quellen.

Pflichtoptionen:
  --server HOST         Servername oder IP, ohne Protokoll
  --tokens-file DATEI  Lokale Datei mit quelle-1=TOKEN pro Zeile

Optionen:
  --count ANZAHL       1, 4 oder 8 Quellen (Standard: 1)
  --first-index NR     Erste Quellennummer (Standard: 1)
  --port PORT          RTMP-Port (Standard: 1935)
  --path-prefix TEXT   Empfangspfad vor der Nummer (Standard: quelle-)
  --video DATEI        H.264/AAC-Testclip
  --duration SEK       Laufzeit; 0 läuft bis Strg+C (Standard: 0)
  --log-dir PFAD       Verzeichnis für FFmpeg-Protokolle
  -h, --help           Hilfe anzeigen

Beispiel für die Token-Datei (chmod 600):
  quelle-1=AbCdEf123456
  quelle-2=GhIjKl789012
EOF
}

fail() {
    echo "FEHLER: $*" >&2
    exit 1
}

cleanup() {
    trap - INT TERM EXIT
    if [ "${#PIDS[@]}" -gt 0 ]; then
        echo
        echo "Beende Test-Publisher ..."
        for pid in "${PIDS[@]}"; do
            if kill -0 "${pid}" 2>/dev/null; then
                kill -INT "${pid}" 2>/dev/null || true
            fi
        done
        for pid in "${PIDS[@]}"; do
            wait "${pid}" 2>/dev/null || true
        done
    fi
}
trap cleanup INT TERM EXIT

while [ "$#" -gt 0 ]; do
    case "$1" in
        --server) SERVER="${2:-}"; shift 2 ;;
        --port) PORT="${2:-}"; shift 2 ;;
        --count) COUNT="${2:-}"; shift 2 ;;
        --first-index) FIRST_INDEX="${2:-}"; shift 2 ;;
        --path-prefix) PATH_PREFIX="${2:-}"; shift 2 ;;
        --video) VIDEO="${2:-}"; shift 2 ;;
        --duration) DURATION="${2:-}"; shift 2 ;;
        --tokens-file) TOKENS_FILE="${2:-}"; shift 2 ;;
        --log-dir) LOG_DIR="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) fail "Unbekannte Option: $1" ;;
    esac
done

[ -n "${SERVER}" ] || fail "--server fehlt."
[[ "${SERVER}" =~ ^[A-Za-z0-9.-]+$ ]] ||
    fail "--server darf nur Hostname oder IP enthalten."
[[ "${PORT}" =~ ^[0-9]+$ ]] &&
    [ "${PORT}" -ge 1 ] && [ "${PORT}" -le 65535 ] ||
    fail "Ungültiger RTMP-Port: ${PORT}"
case "${COUNT}" in 1|4|8) ;; *) fail "--count muss 1, 4 oder 8 sein." ;; esac
[[ "${FIRST_INDEX}" =~ ^[1-8]$ ]] ||
    fail "--first-index muss zwischen 1 und 8 liegen."
[ $((FIRST_INDEX + COUNT - 1)) -le 8 ] ||
    fail "Der gewählte Bereich überschreitet Quelle 8."
[[ "${DURATION}" =~ ^[0-9]+$ ]] ||
    fail "--duration muss eine ganze Zahl sein."
[[ "${PATH_PREFIX}" =~ ^[a-z0-9_-]+$ ]] ||
    fail "--path-prefix enthält ungültige Zeichen."
[ -f "${VIDEO}" ] ||
    fail "Testvideo fehlt: ${VIDEO}. Zuerst generate-test-video.sh ausführen."
[ -n "${TOKENS_FILE}" ] && [ -f "${TOKENS_FILE}" ] ||
    fail "Eine vorhandene --tokens-file ist erforderlich."
command -v "${FFMPEG_BIN}" >/dev/null 2>&1 || fail "FFmpeg fehlt."

if [ "$(uname -s)" = "Linux" ]; then
    token_mode="$(stat -c '%a' "${TOKENS_FILE}")"
else
    token_mode="$(stat -f '%Lp' "${TOKENS_FILE}")"
fi
if [ $((8#${token_mode} & 8#077)) -ne 0 ]; then
    fail "Token-Datei ist für Gruppe/Andere lesbar. Bitte: chmod 600 '${TOKENS_FILE}'"
fi

if command -v "${FFPROBE_BIN}" >/dev/null 2>&1; then
    video_codec="$("${FFPROBE_BIN}" -v error -select_streams v:0 \
        -show_entries stream=codec_name -of csv=p=0 "${VIDEO}")"
    [ "${video_codec}" = "h264" ] ||
        fail "Das Testvideo muss H.264 enthalten (gefunden: ${video_codec:-nichts})."
    has_b_frames="$("${FFPROBE_BIN}" -v error -select_streams v:0 \
        -show_entries stream=has_b_frames -of csv=p=0 "${VIDEO}")"
    [ "${has_b_frames}" = "0" ] ||
        fail "Das Testvideo enthält B-Frames und ist nicht WebRTC-kompatibel."
else
    video_info="$("${FFMPEG_BIN}" -hide_banner -i "${VIDEO}" \
        -t 0 -f null - 2>&1 || true)"
    grep -q 'Video: h264' <<<"${video_info}" ||
        fail "Das Testvideo enthält keinen erkennbaren H.264-Stream."
    frame_info="$("${FFMPEG_BIN}" -hide_banner -loglevel info \
        -i "${VIDEO}" -an -t 5 -vf showinfo -f null - 2>&1 || true)"
    if grep -q 'type:B' <<<"${frame_info}"; then
        fail "Das Testvideo enthält B-Frames und ist nicht WebRTC-kompatibel."
    fi
fi

token_for() {
    local source_id="$1"
    awk -F= -v source_id="${source_id}" \
        '$1 == source_id {sub(/^[^=]*=/, ""); print; exit}' \
        "${TOKENS_FILE}"
}

mkdir -p "${LOG_DIR}"
echo "Mehrquellen-Test"
echo "  Server:     ${SERVER}:${PORT}"
echo "  Quellen:    ${COUNT} ab ${PATH_PREFIX}${FIRST_INDEX}"
echo "  Testvideo:  ${VIDEO}"
if [ "${DURATION}" -eq 0 ]; then
    echo "  Laufzeit:   bis Strg+C"
else
    echo "  Laufzeit:   ${DURATION} s"
fi
echo "  Protokolle: ${LOG_DIR}"

for ((offset = 0; offset < COUNT; offset++)); do
    index=$((FIRST_INDEX + offset))
    source_id="${PATH_PREFIX}${index}"
    token="$(token_for "${source_id}")"
    [ -n "${token}" ] || fail "Kein Token für ${source_id} gefunden."
    [[ "${token}" =~ ^[A-Za-z0-9_-]{12}$ ]] ||
        fail "Token für ${source_id} muss genau 12 URL-sichere Zeichen enthalten."
    target="rtmp://${SERVER}:${PORT}/${source_id}?token=${token}"
    log_file="${LOG_DIR}/${source_id}.log"

    echo "Starte ${source_id} ..."
    "${FFMPEG_BIN}" -hide_banner -nostdin -loglevel warning \
        -re -stream_loop -1 -i "${VIDEO}" \
        -map 0:v:0 -map '0:a:0?' \
        -c copy -flvflags no_duration_filesize \
        -f flv "${target}" \
        >"${log_file}" 2>&1 &
    PIDS+=("$!")
    SOURCE_IDS+=("${source_id}")
    sleep 1
done

echo "Alle Publisher gestartet. Status in Open BOS Stream kontrollieren."
started_at="${SECONDS}"
while true; do
    failed=false
    for position in "${!PIDS[@]}"; do
        if ! kill -0 "${PIDS[${position}]}" 2>/dev/null; then
            echo "Publisher ${SOURCE_IDS[${position}]} wurde unerwartet beendet." >&2
            echo "Siehe ${LOG_DIR}/${SOURCE_IDS[${position}]}.log" >&2
            failed=true
        fi
    done
    [ "${failed}" = false ] || exit 1
    if [ "${DURATION}" -gt 0 ] &&
        [ $((SECONDS - started_at)) -ge "${DURATION}" ]; then
        echo "Testlauf nach ${DURATION} Sekunden abgeschlossen."
        exit 0
    fi
    sleep 2
done

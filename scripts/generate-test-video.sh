#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT="${PROJECT_DIR}/testdata/open-bos-test-720p.mp4"
DURATION=60
FORCE=false
FFMPEG_BIN="${FFMPEG_BIN:-ffmpeg}"
FFPROBE_BIN="${FFPROBE_BIN:-ffprobe}"

usage() {
    cat <<'EOF'
Verwendung: generate-test-video.sh [Optionen]

Erzeugt einen reproduzierbaren H.264/AAC-Testclip für RTMP-Dauertests.

Optionen:
  --output DATEI     Zielpfad (Standard: testdata/open-bos-test-720p.mp4)
  --duration SEK     Cliplänge, mindestens 10 Sekunden (Standard: 60)
  --force            Vorhandene Zieldatei ersetzen
  -h, --help         Hilfe anzeigen
EOF
}

fail() {
    echo "FEHLER: $*" >&2
    exit 1
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --output) OUTPUT="${2:-}"; shift 2 ;;
        --duration) DURATION="${2:-}"; shift 2 ;;
        --force) FORCE=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) fail "Unbekannte Option: $1" ;;
    esac
done

command -v "${FFMPEG_BIN}" >/dev/null 2>&1 ||
    fail "FFmpeg fehlt. Unter Debian: apt install ffmpeg"
[[ "${DURATION}" =~ ^[0-9]+$ ]] ||
    fail "--duration muss eine ganze Zahl sein."
[ "${DURATION}" -ge 10 ] ||
    fail "Der Testclip muss mindestens 10 Sekunden lang sein."
ENCODER_LIST="$("${FFMPEG_BIN}" -hide_banner -encoders 2>/dev/null)"
grep -qE '^[[:space:]]*V[^ ]*[[:space:]]+libx264([[:space:]]|$)' \
    <<<"${ENCODER_LIST}" ||
    fail "Dieser FFmpeg-Build enthält den benötigten Encoder libx264 nicht."

if [ -e "${OUTPUT}" ] && [ "${FORCE}" != true ]; then
    fail "Zieldatei existiert bereits. --force verwenden: ${OUTPUT}"
fi

mkdir -p "$(dirname "${OUTPUT}")"
TEMPORARY="${OUTPUT}.new"
trap 'rm -f -- "${TEMPORARY}"' EXIT

echo "Erzeuge ${DURATION} Sekunden synthetisches 720p-Testvideo ..."
"${FFMPEG_BIN}" -hide_banner -loglevel warning -y \
    -f lavfi -i "testsrc2=size=1280x720:rate=25" \
    -f lavfi -i "sine=frequency=1000:sample_rate=48000" \
    -t "${DURATION}" \
    -map 0:v:0 -map 1:a:0 \
    -c:v libx264 -preset veryfast -tune zerolatency \
    -profile:v baseline -level:v 3.1 -pix_fmt yuv420p \
    -b:v 2M -maxrate 2M -bufsize 4M \
    -g 50 -keyint_min 50 -sc_threshold 0 -bf 0 \
    -c:a aac -b:a 96k -ar 48000 -ac 1 \
    -movflags +faststart \
    -f mp4 \
    "${TEMPORARY}"

if command -v "${FFPROBE_BIN}" >/dev/null 2>&1; then
    "${FFPROBE_BIN}" -v error -select_streams v:0 \
        -show_entries stream=codec_name,width,height,avg_frame_rate \
        -of default=noprint_wrappers=1 "${TEMPORARY}"
else
    echo "Hinweis: ffprobe fehlt; überspringe die optionale Metadatenanzeige."
fi

mv -- "${TEMPORARY}" "${OUTPUT}"
trap - EXIT
echo "Testvideo erstellt: ${OUTPUT}"

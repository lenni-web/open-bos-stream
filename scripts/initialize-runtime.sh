#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

echo
echo "Initialisiere Laufzeitumgebung ..."
echo

RUNTIME_DIRS=(
    config
    mapdata
    recordings
    snapshots
)

for dir in "${RUNTIME_DIRS[@]}"; do
    sudo mkdir -p "${TARGET_DIR}/${dir}"
done

#
# Standard-Konfiguration nur bei Neuinstallation übernehmen.
# stream.yaml ist eine lokale Laufzeitdatei und wird nicht von Git verwaltet.
#
DEFAULT_CONFIG="${PROJECT_DIR}/config/stream.example.yaml"
RUNTIME_CONFIG="${TARGET_DIR}/config/stream.yaml"

if [ ! -e "${RUNTIME_CONFIG}" ]; then
    if [ ! -f "${DEFAULT_CONFIG}" ]; then
        echo "FEHLER: Standard-Konfiguration fehlt: ${DEFAULT_CONFIG}" >&2
        exit 1
    fi

    sudo install \
        --mode=0640 \
        "${DEFAULT_CONFIG}" \
        "${RUNTIME_CONFIG}"
fi

#
# Standard-Kartendaten nur bei Neuinstallation übernehmen
#
if [ -d "${PROJECT_DIR}/mapdata" ]; then

    sudo rsync \
        --archive \
        --ignore-existing \
        "${PROJECT_DIR}/mapdata/" \
        "${TARGET_DIR}/mapdata/"
fi

#
# Medien aus älteren Installationen verlustfrei übernehmen.
# Die Quelldateien bleiben als Sicherung erhalten und bereits
# vorhandene Zieldateien werden nicht überschrieben.
#
for media_dir in recordings snapshots; do

    if [ -d "${PROJECT_DIR}/${media_dir}" ]; then

        echo "Übernehme vorhandene ${media_dir} ..."

        sudo rsync \
            --archive \
            --ignore-existing \
            "${PROJECT_DIR}/${media_dir}/" \
            "${TARGET_DIR}/${media_dir}/"
    fi
done

echo
echo
echo "Setze Besitzer und Gruppen ..."

sudo chown -R "${SERVICE_USER}:${SERVICE_GROUP}" \
    "${TARGET_DIR}/config"

sudo chown -R "${SERVICE_USER}:${SERVICE_GROUP}" \
    "${TARGET_DIR}/mapdata"

sudo chown -R "${SERVICE_USER}:${SERVICE_GROUP}" \
    "${TARGET_DIR}/recordings"

sudo chown -R "${SERVICE_USER}:${SERVICE_GROUP}" \
    "${TARGET_DIR}/snapshots"
echo
echo "Laufzeitumgebung bereit."

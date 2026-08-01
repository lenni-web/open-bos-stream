#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

validate_service_identity "${SERVICE_USER}" "${SERVICE_GROUP}"

echo
echo "Prüfe Dienstidentität ${SERVICE_USER}:${SERVICE_GROUP} ..."

if ! getent group "${SERVICE_GROUP}" >/dev/null 2>&1; then
    echo "Lege Gruppe ${SERVICE_GROUP} an ..."
    sudo groupadd --system "${SERVICE_GROUP}"
fi

if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
    echo "Lege Dienstbenutzer ${SERVICE_USER} an ..."
    sudo useradd \
        --create-home \
        --shell /bin/bash \
        --gid "${SERVICE_GROUP}" \
        --comment "Open BOS Stream service account" \
        "${SERVICE_USER}"
elif ! id -nG "${SERVICE_USER}" | tr ' ' '\n' | grep -Fxq "${SERVICE_GROUP}"; then
    echo "Ergänze ${SERVICE_USER} um Gruppe ${SERVICE_GROUP} ..."
    sudo usermod --append --groups "${SERVICE_GROUP}" "${SERVICE_USER}"
fi

temporary="$(mktemp)"
trap 'rm -f "${temporary}"' EXIT
{
    printf 'SERVICE_USER=%s\n' "${SERVICE_USER}"
    printf 'SERVICE_GROUP=%s\n' "${SERVICE_GROUP}"
} > "${temporary}"

sudo install -d -m 0755 "${PROFILE_DIR}"
sudo install -o root -g root -m 0644 \
    "${temporary}" "${INSTALL_CONFIG_FILE}"

echo "Dienstidentität bereit: ${SERVICE_USER}:${SERVICE_GROUP}"

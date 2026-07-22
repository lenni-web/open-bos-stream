#!/bin/bash

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

VERSION="$(
    python3 <<EOF
import pathlib
import runpy

version_file = pathlib.Path("${PROJECT_DIR}") / "src" / "open_bos_stream" / "version.py"

try:
    namespace = runpy.run_path(version_file)
    print(namespace.get("VERSION", "unknown"))
except Exception:
    print("unknown")
EOF
)"

APP_NAME="$(
    python3 <<EOF
import pathlib
import runpy

ns = runpy.run_path(
    pathlib.Path("${PROJECT_DIR}") / "src" / "open_bos_stream" / "version.py"
)

print(ns.get("APP_NAME", "Open BOS Stream"))
EOF
)"

COMMIT="unknown"

if git -C "${PROJECT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    COMMIT="$(
        git -C "${PROJECT_DIR}" rev-parse --short HEAD
    )"
fi

BUILD_DATE="$(
    date '+%Y-%m-%d %H:%M:%S'
)"

cat <<EOF | sudo tee "${TARGET_DIR}/.deployment" >/dev/null
Version=${VERSION}
Commit=${COMMIT}
Installed=${BUILD_DATE}
EOF

echo
echo "Deployment-Information geschrieben:"
cat "${TARGET_DIR}/.deployment"

#!/usr/bin/env bash
# Prüft eigene Frontend-Dateien: JavaScript-Syntax (node --check) sowie
# einheitliche Formatierung (keine Tabulatoren, keine Leerzeichen am
# Zeilenende) in JavaScript, CSS und HTML-Templates.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATIC="${ROOT}/src/open_bos_stream/static"
TEMPLATES="${ROOT}/src/open_bos_stream/templates"
status=0

for script in "${STATIC}"/js/*.js; do
    if ! node --check "${script}"; then
        echo "Syntaxfehler: ${script#"${ROOT}/"}" >&2
        status=1
    fi
done

while IFS= read -r file; do
    if grep -n $'\t' "${file}" >/dev/null; then
        echo "Tabulator gefunden: ${file#"${ROOT}/"}" >&2
        grep -n $'\t' "${file}" | head -3 >&2
        status=1
    fi
    if grep -nE ' +$' "${file}" >/dev/null; then
        echo "Leerzeichen am Zeilenende: ${file#"${ROOT}/"}" >&2
        grep -nE ' +$' "${file}" | head -3 >&2
        status=1
    fi
done < <(find "${STATIC}/js" "${STATIC}/css" "${TEMPLATES}" -type f \
    \( -name '*.js' -o -name '*.css' -o -name '*.html' \))

exit "${status}"

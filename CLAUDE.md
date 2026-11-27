# Open BOS Stream – Hinweise für Claude Code

Lage- und Dokumentationssystem für Drohneneinheiten der Feuerwehren
(Livebilder, Einsätze, Karte, Wetter, Checklisten). Sprache für Oberfläche,
Changelog und Commits: **Deutsch**.

## Stack

- FastAPI (`src/open_bos_stream/main.py`), Rollen-Dependencies in `auth/`
  (GUEST, VIEWER, OPERATOR, ADMIN, SERVER_ADMIN, SUPERADMIN, PUBLIC)
- SQLite + SQLAlchemy Core, Migrationen mit Alembic unter
  `db/migrations/versions/` (fortlaufend `000N_name.py`)
- Jinja-Templates (`templates/`, Bausteine in `templates/components/`),
  Vanilla-JS (`static/js/`), CSS (`static/css/`), MapLibre 6
- Organisationsbaum Landkreis → Samtgemeinde → Ortswehr (`org/service.py`);
  Änderungen über `audit()` erhöhen `org.revision` (Rechte-Cache)
- Server-Profil: Caddy, MediaMTX, UFW (`scripts/`)

## Entwicklung (Mac)

- venv liegt außerhalb des Repos: `~/.venvs/open-bos-stream` (Python 3.13).
  Das `.venv` im Repo ist ein Linux-venv und auf dem Mac unbrauchbar.
- Tests: `PYTHONPATH=src ~/.venvs/open-bos-stream/bin/python -m pytest -q`
- Lokaler Server:
  `PYTHONPATH=src ~/.venvs/open-bos-stream/bin/python -m uvicorn open_bos_stream.main:app --host 127.0.0.1 --port 8031`
  Login-API ist `POST /auth/login` (nicht `/api/...`). `config/` enthält
  lokale Daten (DB, stream.yaml) – vor Experimenten sichern, danach
  zurückspielen.
- Statische Dateien hängen `?v=<VERSION>` an; ohne Versionssprung hält der
  Browser alte JS/CSS-Dateien – beim lokalen Testen hart neu laden.
- Neue UI-Elemente: `tests/test_ui_contract.py` prüft Struktur und CSS.

## Release-Ablauf (nur wenn der Nutzer es verlangt)

1. `CHANGELOG.md`: „## [Unreleased]“ → „## [x.y.z] - JJJJ-MM-TT“, neues
   leeres Unreleased darüber
2. `ROADMAP.md`: Eintrag unter „Letzte Releases“
3. Version in `src/open_bos_stream/version.py` und
   `tests/test_server_profile.py`
4. Tests grün → Commit „release: version x.y.z“ → `git tag vx.y.z` →
   `git push origin main` und `git push origin vx.y.z`

## Regeln

- Interne Entwürfe (`docs/entwurf-*`) sind gitignored und werden nie
  veröffentlicht.
- Widmung in der Oberfläche beibehalten: „Gemacht für die Freiwilligen
  Feuerwehren – mit Dank an alle Ehrenamtlichen, besonders der FF
  Agathenburg.“
- Zugangsdaten (DJI App Key/License, Tokens) nie ins Repository oder in den
  Chat – nur in Konfigurationsdateien auf dem Server.
- Fokus: Server-Profil; die Kiosk-Anzeige (`display/`) ist eingefroren.
- Fahrplan und offene Punkte: `ROADMAP.md`.

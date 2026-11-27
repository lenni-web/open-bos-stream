"""Gemeinsame Testumgebung.

Die Tests verwenden eine feste Konfiguration aus ``tests/fixtures`` statt der
lokalen, nicht versionierten ``config/stream.yaml``. Dadurch laufen sie
lokal und in der CI identisch. Die Datei wird in ein temporäres Verzeichnis
kopiert, weil einzelne Dienste die Konfiguration speichern können.
"""

import os
import shutil
import tempfile
from pathlib import Path


_FIXTURE = Path(__file__).parent / "fixtures" / "stream.yaml"
_CONFIG_DIR = Path(tempfile.mkdtemp(prefix="open-bos-test-config-"))
shutil.copyfile(_FIXTURE, _CONFIG_DIR / "stream.yaml")

os.environ["OPEN_BOS_STREAM_CONFIG"] = str(_CONFIG_DIR / "stream.yaml")

# Passwort-Hashing in Tests günstiger rechnen; den Produktivwert und die
# Neuberechnung beim Anmelden prüft tests/test_auth_hardening.py.
from open_bos_stream.auth.service import AuthService  # noqa: E402

if not hasattr(AuthService, "production_iterations"):
    AuthService.production_iterations = AuthService.PASSWORD_ITERATIONS
AuthService.PASSWORD_ITERATIONS = 20_000

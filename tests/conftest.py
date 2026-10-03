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

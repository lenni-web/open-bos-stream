"""
Gemeinsame Dateibibliothek.
"""

from __future__ import annotations

from pathlib import Path


class FileLibrary:
    """Basisklasse für dateibasierte Bibliotheken."""

    extension: str = ""
    
    media_type: str = "file"

    def __init__(self, directory: str) -> None:

        self.directory = Path(directory).resolve()
        self.directory.mkdir(exist_ok=True)

    def list(self) -> list[dict]:
        """Liefert alle Dateien."""

        files: list[dict] = []

        for file in sorted(
            self.directory.glob(f"*{self.extension}"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        ):

            stat = file.stat()

            files.append(
                {
                    "type": self.media_type,
                    "name": file.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                }
            )

        return files

    def get_file(
        self,
        filename: str,
    ) -> Path | None:
        """Liefert eine gültige Datei."""

        if Path(filename).name != filename:
            return None

        file = (
            self.directory /
            filename
        ).resolve()

        try:

            file.relative_to(
                self.directory
            )

        except ValueError:

            return None

        if not file.exists():

            return None

        return file

    def delete(
        self,
        filename: str,
    ) -> bool:
        """Löscht eine Datei."""

        file = self.get_file(
            filename
        )

        if file is None:

            return False

        file.unlink()

        return True

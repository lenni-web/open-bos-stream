"""Verbindung zur SQLite-Datenbank und automatische Migration."""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool


logger = logging.getLogger(__name__)

MIGRATIONS = Path(__file__).parent / "migrations"


class Database:
    """SQLite-Datei; ohne Pfad im Arbeitsspeicher (Tests)."""

    def __init__(self, path: Path | str | None) -> None:
        self.path = Path(path) if path else None
        if self.path is None:
            self.engine: Engine = create_engine(
                "sqlite://",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.engine = create_engine(
                f"sqlite:///{self.path}",
                connect_args={"check_same_thread": False, "timeout": 10},
            )
        file_backed = self.path is not None

        @event.listens_for(self.engine, "connect")
        def _configure(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=10000")
            if file_backed:
                # Gleichzeitiges Lesen während eines Schreibvorgangs.
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    def migrate(self) -> None:
        """Datenbank auf den aktuellen Stand bringen (idempotent)."""

        config = Config()
        config.set_main_option("script_location", str(MIGRATIONS))
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        if self.path is not None:
            self.path.chmod(0o600)

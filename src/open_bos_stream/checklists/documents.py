"""Einheitliche Dokumente des Landkreises (z. B. Merkblätter, Formulare).

Hochladen und Löschen dürfen Drohnenteams und Admins auf Landkreisebene,
ansehen alle angemeldeten Konten. Die Dateien liegen unter zufälligem Namen
in einem eigenen Verzeichnis; der Originalname steht nur in der Datenbank.
"""

from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path

from sqlalchemy import delete, insert, select

from open_bos_stream.checklists.service import (
    ChecklistAccessError,
    ChecklistError,
    ChecklistService,
)
from open_bos_stream.db.schema import documents
from open_bos_stream.incidents.service import iso, local_now

MAX_DOCUMENT_BYTES = 25 * 1024 * 1024

ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".txt": "text/plain; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


class DocumentStore:
    def __init__(self, checklists: ChecklistService, directory: str | Path) -> None:
        self.checklists = checklists
        self.directory = Path(directory)

    @property
    def _engine(self):
        return self.checklists.org.db.engine

    def list(self) -> list[dict]:
        with self._engine.connect() as connection:
            rows = connection.execute(select(documents).order_by(documents.c.title)).all()
        return [dict(row._mapping) for row in rows]

    def get(self, document_id: int) -> dict | None:
        with self._engine.connect() as connection:
            row = connection.execute(select(documents).where(documents.c.id == document_id)).first()
        return dict(row._mapping) if row else None

    def path(self, document: dict) -> Path:
        return self.directory / document["stored_name"]

    def upload(
        self,
        user: dict,
        *,
        filename: str,
        data: bytes,
        title: str = "",
        description: str = "",
    ) -> dict:
        if not self.checklists.can_manage_templates(user):
            raise ChecklistAccessError(
                "Dokumente stellen Drohnenteams und Admins auf Landkreisebene bereit."
            )
        original = Path(str(filename or "")).name.strip()[:200]
        extension = Path(original).suffix.lower()
        if extension not in ALLOWED_TYPES:
            raise ChecklistError(
                "Erlaubt sind PDF, Word, Excel, PowerPoint, OpenDocument, Text und Bilder (PNG/JPG)."
            )
        if not data:
            raise ChecklistError("Die Datei ist leer.")
        if len(data) > MAX_DOCUMENT_BYTES:
            raise ChecklistError("Die Datei ist zu groß (höchstens 25 MB).")
        title = " ".join(str(title or "").split())[:120] or Path(original).stem[:120]
        stored = secrets.token_hex(16) + extension
        self.directory.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".upload.", dir=self.directory)
        try:
            os.chmod(temporary, 0o640)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
            os.replace(temporary, self.directory / stored)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        actor = user.get("display_name") or user["username"]
        try:
            with self._engine.begin() as connection:
                document_id = connection.execute(insert(documents).values(
                    organization_id=self.checklists.template_owner(user),
                    title=title,
                    description=" ".join(str(description or "").split())[:500],
                    stored_name=stored,
                    original_name=original,
                    content_type=ALLOWED_TYPES[extension],
                    size=len(data),
                    uploaded_by=actor,
                    uploaded_at=iso(local_now()),
                )).inserted_primary_key[0]
        except BaseException:
            (self.directory / stored).unlink(missing_ok=True)
            raise
        self.checklists.org.audit(actor, "Dokument bereitgestellt", title)
        return self.get(document_id)

    def delete(self, user: dict, document_id: int) -> None:
        if not self.checklists.can_manage_templates(user):
            raise ChecklistAccessError("Dokumente verwalten Drohnenteams und Admins auf Landkreisebene.")
        document = self.get(document_id)
        if document is None:
            raise LookupError("Dokument nicht gefunden.")
        with self._engine.begin() as connection:
            connection.execute(delete(documents).where(documents.c.id == document_id))
        self.path(document).unlink(missing_ok=True)
        self.checklists.org.audit(user.get("display_name") or user["username"], "Dokument gelöscht", document["title"])

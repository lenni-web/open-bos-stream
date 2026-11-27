"""Checklisten-Modul: Vorlagen, Listen (eigene und im Einsatz), Dokumente."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from open_bos_stream.auth.roles import VIEWER
from open_bos_stream.checklists.documents import MAX_DOCUMENT_BYTES, DocumentStore
from open_bos_stream.checklists.service import (
    ChecklistAccessError,
    ChecklistError,
    ChecklistService,
)
from open_bos_stream.core.container import auth_service, documents_directory

router = APIRouter(
    dependencies=[VIEWER],
    prefix="/api/checklists",
    tags=["Checklisten"],
)
documents_router = APIRouter(
    dependencies=[VIEWER],
    prefix="/api/documents",
    tags=["Dokumente"],
)


def _service() -> ChecklistService:
    auth_service.ready()
    return ChecklistService(auth_service.incidents)


def _documents() -> DocumentStore:
    return DocumentStore(_service(), documents_directory)


def _user(request: Request) -> dict:
    user = request.state.user
    if user.get("role") == "guest":
        raise HTTPException(status_code=403, detail="Nur für angemeldete Konten.")
    return user


async def _call(function, *args, **kwargs):
    try:
        return await run_in_threadpool(lambda: function(*args, **kwargs))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'\"")) from exc
    except (ChecklistAccessError, PermissionError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ChecklistError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _org_names(service: ChecklistService) -> dict[int, str]:
    return {
        item["id"]: item["short_name"] or item["name"]
        for item in service.org.organizations()
    }


class ItemIn(BaseModel):
    text: str = Field(max_length=300)
    section: str = Field(default="", max_length=80)
    hint: str = Field(default="", max_length=300)
    required: bool = False


# ----------------------------------------------------------------------
# Übersicht
# ----------------------------------------------------------------------


@router.get("")
async def overview(request: Request) -> dict:
    user = _user(request)
    service = _service()
    manager = service.can_manage_templates(user)
    lists = await run_in_threadpool(service.visible, user)
    templates = await run_in_threadpool(service.templates, include_archived=manager)
    names = await run_in_threadpool(_org_names, service)
    return {
        "checklists": [item | {"organization_name": names.get(item["organization_id"], "?")} for item in lists],
        "templates": [
            {key: item[key] for key in (
                "id", "title", "description", "item_count", "required_count",
                "version", "archived", "updated_at", "updated_by",
            )}
            for item in templates
        ],
        "can_manage_templates": manager,
        "organizations": [
            {"id": organization_id, "name": names.get(organization_id, "?")}
            for organization_id in service.lead_options(user)
        ],
    }


# ----------------------------------------------------------------------
# Vorlagen (vor /{checklist_id}, damit „templates“ kein Listen-Id ist)
# ----------------------------------------------------------------------


class TemplateIn(BaseModel):
    title: str = Field(max_length=120)
    description: str = Field(default="", max_length=2000)
    items: list[ItemIn] = Field(default_factory=list, max_length=200)


class TemplateUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    items: list[ItemIn] | None = Field(default=None, max_length=200)
    archived: bool | None = None


@router.get("/templates/{template_id}")
async def get_template(template_id: int, request: Request) -> dict:
    _user(request)
    template = await run_in_threadpool(_service().template, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden.")
    return {"template": template}


@router.post("/templates")
async def create_template(payload: TemplateIn, request: Request) -> dict:
    user = _user(request)
    data = payload.model_dump()
    template = await _call(_service().create_template, user, **data)
    return {"success": True, "template": template}


@router.put("/templates/{template_id}")
async def update_template(template_id: int, payload: TemplateUpdate, request: Request) -> dict:
    user = _user(request)
    template = await _call(_service().update_template, user, template_id, **payload.model_dump(exclude_unset=True))
    return {"success": True, "template": template}


@router.delete("/templates/{template_id}")
async def delete_template(template_id: int, request: Request) -> dict:
    user = _user(request)
    await _call(_service().delete_template, user, template_id)
    return {"success": True}


# ----------------------------------------------------------------------
# Listen
# ----------------------------------------------------------------------


class ChecklistIn(BaseModel):
    title: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=2000)
    template_id: int | None = None
    incident_id: int | None = None
    organization_id: int | None = None
    items: list[ItemIn] = Field(default_factory=list, max_length=200)


class ChecklistUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class ItemUpdate(BaseModel):
    checked: bool | None = None
    note: str | None = Field(default=None, max_length=1000)


class StatusIn(BaseModel):
    status: str = Field(max_length=16)


def _with_names(checklist: dict) -> dict:
    service = _service()
    names = _org_names(service)
    result = checklist | {"organization_name": names.get(checklist["organization_id"], "?")}
    if checklist.get("incident_id"):
        incident = service.incidents.get(checklist["incident_id"])
        result["incident"] = (
            {key: incident[key] for key in ("id", "code", "keyword", "status", "exercise")}
            if incident else None
        )
    return result


@router.post("")
async def create_checklist(payload: ChecklistIn, request: Request) -> dict:
    user = _user(request)
    data = payload.model_dump()
    checklist = await _call(_service().create, user, **data)
    return {"success": True, "checklist": await run_in_threadpool(_with_names, checklist)}


@router.get("/{checklist_id}")
async def get_checklist(checklist_id: int, request: Request) -> dict:
    user = _user(request)
    checklist = await _call(_service().require, user, checklist_id)
    return {"checklist": await run_in_threadpool(_with_names, checklist)}


@router.patch("/{checklist_id}")
async def update_checklist(checklist_id: int, payload: ChecklistUpdate, request: Request) -> dict:
    user = _user(request)
    checklist = await _call(_service().update, user, checklist_id, **payload.model_dump(exclude_unset=True))
    return {"checklist": await run_in_threadpool(_with_names, checklist)}


@router.delete("/{checklist_id}")
async def delete_checklist(checklist_id: int, request: Request) -> dict:
    user = _user(request)
    await _call(_service().delete, user, checklist_id)
    return {"success": True}


@router.post("/{checklist_id}/status")
async def checklist_status(checklist_id: int, payload: StatusIn, request: Request) -> dict:
    user = _user(request)
    checklist = await _call(_service().set_status, user, checklist_id, payload.status)
    return {"checklist": await run_in_threadpool(_with_names, checklist)}


@router.put("/{checklist_id}/items/{item_id}")
async def set_item(checklist_id: int, item_id: int, payload: ItemUpdate, request: Request) -> dict:
    user = _user(request)
    checklist = await _call(
        _service().set_item, user, checklist_id, item_id,
        checked=payload.checked, note=payload.note,
    )
    return {"checklist": await run_in_threadpool(_with_names, checklist)}


@router.post("/{checklist_id}/items")
async def add_item(checklist_id: int, payload: ItemIn, request: Request) -> dict:
    user = _user(request)
    checklist = await _call(_service().add_item, user, checklist_id, **payload.model_dump())
    return {"checklist": await run_in_threadpool(_with_names, checklist)}


@router.delete("/{checklist_id}/items/{item_id}")
async def remove_item(checklist_id: int, item_id: int, request: Request) -> dict:
    user = _user(request)
    checklist = await _call(_service().remove_item, user, checklist_id, item_id)
    return {"checklist": await run_in_threadpool(_with_names, checklist)}


# ----------------------------------------------------------------------
# Dokumente
# ----------------------------------------------------------------------


@documents_router.get("")
async def list_documents(request: Request) -> dict:
    user = _user(request)
    store = _documents()
    items = await run_in_threadpool(store.list)
    return {
        "documents": [
            {key: item[key] for key in (
                "id", "title", "description", "original_name", "content_type",
                "size", "uploaded_by", "uploaded_at",
            )}
            for item in items
        ],
        "can_manage": store.checklists.can_manage_templates(user),
        "max_bytes": MAX_DOCUMENT_BYTES,
    }


@documents_router.post("")
async def upload_document(
    request: Request,
    filename: str,
    title: str = "",
    description: str = "",
) -> dict:
    """Datei als Rohdaten im Body (ohne Formular-Bibliothek)."""

    user = _user(request)
    length = int(request.headers.get("content-length") or 0)
    if length > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="Die Datei ist zu groß (höchstens 25 MB).")
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_DOCUMENT_BYTES:
            raise HTTPException(status_code=413, detail="Die Datei ist zu groß (höchstens 25 MB).")
    document = await _call(
        _documents().upload, user,
        filename=filename, data=bytes(data), title=title, description=description,
    )
    return {"success": True, "document": {k: v for k, v in document.items() if k != "stored_name"}}


@documents_router.get("/{document_id}/file")
async def document_file(document_id: int, request: Request, download: bool = False):
    _user(request)
    store = _documents()
    document = await run_in_threadpool(store.get, document_id)
    if document is None or not store.path(document).exists():
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path=store.path(document),
        media_type=document["content_type"],
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(document['original_name'])}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@documents_router.delete("/{document_id}")
async def delete_document(document_id: int, request: Request) -> dict:
    user = _user(request)
    await _call(_documents().delete, user, document_id)
    return {"success": True}

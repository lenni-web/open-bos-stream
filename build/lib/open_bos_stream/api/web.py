from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from open_bos_stream.version import VERSION
from open_bos_stream.auth.service import ROLE_LEVEL
from open_bos_stream.db.schema import MEMBERSHIP_ROLES
from open_bos_stream.core.container import auth_service
from open_bos_stream.core.installation import installation_profile
from open_bos_stream.auth.roles import PUBLIC, VIEWER

router = APIRouter(tags=["Web"])

templates = Jinja2Templates(
    directory="src/open_bos_stream/templates"
)


def permissions(user: dict) -> dict:
    """Was die Oberfläche einblendet (die Schnittstellen prüfen selbst)."""

    level = ROLE_LEVEL.get(user.get("role"), 0)
    superadmin = user.get("role") == "superadmin"
    return {
        "operate": level >= ROLE_LEVEL["operator"],
        "admin": level >= ROLE_LEVEL["admin"],
        "server_admin": superadmin or bool(user.get("server_admin"))
        or ("org_view" not in user and level >= ROLE_LEVEL["admin"]),
        "superadmin": superadmin,
    }


def role_summary(user: dict) -> str:
    """z. B. „Wehr-Admin · OF Hagen“ für das Benutzermenü."""

    if user.get("role") == "superadmin":
        return "Superadmin"
    if "user_id" not in user:
        return {"viewer": "Zuschauer", "admin": "Admin"}.get(user.get("role"), "")
    org = auth_service.ready()
    names = {
        item["id"]: item["short_name"] or item["name"]
        for item in org.organizations()
    }
    parts = [
        f"{MEMBERSHIP_ROLES.get(item['role'], item['role'])} · "
        f"{names.get(item['organization_id'], '?')}"
        for item in org.memberships(user["user_id"])
    ]
    return ", ".join(parts) or "Ohne Organisation"


@router.get("/", response_class=HTMLResponse, dependencies=[VIEWER])
async def dashboard(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "host": request.url.hostname,
            "version": VERSION,
            "user": request.state.user,
            "can": permissions(request.state.user),
            "role_summary": role_summary(request.state.user),
            "installation_profile": installation_profile(),
            # Für direkte MediaMTX-Abrufe ohne Caddy (WHEP/HLS).
            "media_token": auth_service.create_media_token(
                request.state.user
            ),
        },
    )


@router.get("/login", response_class=HTMLResponse, dependencies=[PUBLIC])
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "version": VERSION,
        },
    )


@router.get("/display/stream", response_class=HTMLResponse, dependencies=[PUBLIC])
async def display_stream(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="display_stream.html",
        context={
            "request": request,
            "version": VERSION,
        },
    )

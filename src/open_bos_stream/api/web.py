from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from open_bos_stream.version import VERSION
from open_bos_stream.core.installation import installation_profile

router = APIRouter(tags=["Web"])

templates = Jinja2Templates(
    directory="src/open_bos_stream/templates"
)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "host": request.url.hostname,
            "version": VERSION,
            "user": request.state.user,
            "installation_profile": installation_profile(),
        },
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "version": VERSION,
        },
    )


@router.get("/display/stream", response_class=HTMLResponse)
async def display_stream(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="display_stream.html",
        context={
            "request": request,
            "version": VERSION,
        },
    )

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from open_bos_stream.version import VERSION

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
        },
    )

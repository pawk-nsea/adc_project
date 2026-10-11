"""Employee-facing web page served by the same FastAPI process."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response


WEB_DIRECTORY = Path(__file__).parent.parent / "web"
INDEX_HTML = (WEB_DIRECTORY / "index.html").read_text(encoding="utf-8")
STYLES_CSS = (WEB_DIRECTORY / "styles.css").read_text(encoding="utf-8")
APP_JAVASCRIPT = (WEB_DIRECTORY / "app.js").read_text(encoding="utf-8")

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
async def web_app() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML)


@router.get("/static/styles.css", response_class=Response)
async def web_styles() -> Response:
    return Response(STYLES_CSS, media_type="text/css")


@router.get("/static/app.js", response_class=Response)
async def web_javascript() -> Response:
    return Response(APP_JAVASCRIPT, media_type="text/javascript")

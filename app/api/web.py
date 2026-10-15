"""Serve the browser page and static assets from the same FastAPI process."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response


WEB_DIRECTORY = Path(__file__).parent.parent / "web"
# Assets are read at import time; reload the module to pick up edits.
INDEX_HTML = (WEB_DIRECTORY / "index.html").read_text(encoding="utf-8")
STYLES_CSS = (WEB_DIRECTORY / "styles.css").read_text(encoding="utf-8")
APP_JAVASCRIPT = (WEB_DIRECTORY / "app.js").read_text(encoding="utf-8")

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
async def web_app() -> HTMLResponse:
    """Return the cached workspace page; no template rendering is performed."""

    return HTMLResponse(INDEX_HTML)


@router.get("/static/styles.css", response_class=Response)
async def web_styles() -> Response:
    """Serve the cached stylesheet with its CSS content type."""

    return Response(STYLES_CSS, media_type="text/css")


@router.get("/static/app.js", response_class=Response)
async def web_javascript() -> Response:
    """Serve the cached browser module with its JavaScript content type."""

    return Response(APP_JAVASCRIPT, media_type="text/javascript")

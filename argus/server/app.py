"""Walking-skeleton FastAPI app for ARGUS lap 1."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from argus.scheduler.cadence import start_scheduler, stop_scheduler
from argus.server.routes_agui import router as agui_router
from argus.server.routes_alerts import router as alerts_router
from argus.server.routes_ask import router as ask_router
from argus.server.routes_enso import router as enso_router
from argus.server.routes_eval import router as eval_router
from argus.server.routes_reports import router as reports_router
from argus.server.routes_spend import router as spend_router
from argus.server.routes_verify import router as verify_router
from argus.server.routes_watches import router as watches_router
from argus.store.db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="ARGUS", lifespan=lifespan)

# Create the database synchronously at import so plain `TestClient(app)`
# usage (without lifespan) still sees `data/argus.db`; the lifespan hook
# above covers real server boots.
init_db()

app.include_router(spend_router)
app.include_router(watches_router)
app.include_router(verify_router)
app.include_router(ask_router)
app.include_router(alerts_router)
app.include_router(agui_router)
app.include_router(reports_router)
app.include_router(eval_router)
app.include_router(enso_router)

_STATIC_DIR = Path(__file__).with_name("static")
_ASSETS_DIR = _STATIC_DIR / "assets"
_PLACEHOLDER = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8" /><title>ARGUS</title></head>
<body><h1>ARGUS &mdash; under construction</h1></body>
</html>"""


if _ASSETS_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=_ASSETS_DIR, html=False), name="assets")


@app.exception_handler(405)
async def method_not_allowed_as_not_found(_request: Request, _exc: Exception) -> JSONResponse:
    # The skeleton exposes no method-specific operations, so a wrong-method
    # call targets an operation that does not exist: report a uniform 404
    # (without reading the body, so malformed payloads never hang or 500).
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


@app.get("/healthz")
@app.get("/api/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    index_file = _STATIC_DIR / "index.html"
    if index_file.is_file():
        return index_file.read_text(encoding="utf-8")
    return _PLACEHOLDER

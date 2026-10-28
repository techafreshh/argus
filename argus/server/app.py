"""Walking-skeleton FastAPI app for ARGUS lap 1."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="ARGUS")

_STATIC_DIR = Path(__file__).with_name("static")
_PLACEHOLDER = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8" /><title>ARGUS</title></head>
<body><h1>ARGUS &mdash; under construction</h1></body>
</html>"""


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

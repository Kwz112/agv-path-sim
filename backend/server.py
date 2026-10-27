"""Local-only standalone AGV simulation service."""
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from .routers.agv import router

app = FastAPI(title="AGV 路径仿真", docs_url=None, redoc_url=None, openapi_url=None)

@app.middleware("http")
async def local_request_only(request: Request, call_next):
    # Reject DNS rebinding and cross-origin browser requests to the local API.
    host = request.headers.get("host", "").lower()
    hostname = host.rsplit(":", 1)[0] if ":" in host else host
    if hostname not in {"127.0.0.1", "localhost"}:
        return JSONResponse({"error": "local host required"}, status_code=403)
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme != "http" or parsed.netloc.lower() != host:
            return JSONResponse({"error": "same origin required"}, status_code=403)
    return await call_next(request)

app.include_router(router, prefix="/api")
_frontend = Path(__file__).resolve().parent.parent / "frontend"

@app.get("/")
async def index():
    return FileResponse(_frontend / "agv-sim.html")

app.mount("/", StaticFiles(directory=str(_frontend), check_dir=False), name="frontend")

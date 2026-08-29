from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from api.routers import auth, collections, comments, investigations, sources
from core.config import get_settings

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(
    title="Zandar OSINT API",
    version="0.1.0",
    description="Platform analisis sentimen & forensik narasi — Fase 0 (fondasi).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(investigations.router, prefix="/api/v1")
app.include_router(sources.router, prefix="/api/v1")
app.include_router(collections.router, prefix="/api/v1")
app.include_router(comments.router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "env": get_settings().zandar_env}


@app.get("/", include_in_schema=False)
async def frontend() -> FileResponse:
    """Sajikan Comment Explorer (single-page, same-origin dengan API)."""
    return FileResponse(WEB_DIR / "index.html")

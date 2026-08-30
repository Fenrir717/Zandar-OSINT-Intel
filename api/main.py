from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routers import (
    analysis,
    auth,
    claims,
    collections,
    comments,
    graph,
    investigations,
    narratives,
    planner,
    projects,
    reports,
    sources,
    system,
)
from core.config import get_settings

DIST_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"

app = FastAPI(
    title="Zandar OSINT API",
    version="0.1.0",
    description="Platform analisis sentimen & forensik narasi — Fase 0 (fondasi).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(investigations.router, prefix="/api/v1")
app.include_router(sources.router, prefix="/api/v1")
app.include_router(collections.router, prefix="/api/v1")
app.include_router(comments.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(planner.router, prefix="/api/v1")
app.include_router(narratives.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(graph.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(claims.router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "env": get_settings().zandar_env}


# Sajikan SPA hasil build (web/dist). Dev pakai Vite di :5173 (proxy /api);
# produksi memakai `npm run build` lalu FastAPI menyajikan file statis ini.
if (DIST_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        # Jangan tangkap rute API/dokumentasi; sisanya → index.html (client routing)
        if full_path.startswith(("api/", "health", "docs", "redoc", "openapi.json")):
            raise HTTPException(status_code=404)
        file = DIST_DIR / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(DIST_DIR / "index.html")
else:

    @app.get("/", include_in_schema=False)
    async def no_build() -> dict:
        return {"detail": "Frontend belum di-build. Jalankan: cd web && npm run build"}

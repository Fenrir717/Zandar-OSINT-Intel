"""Status sistem & pengguna — untuk halaman Settings/Administration."""

import asyncio
import socket
from urllib.parse import urlparse

from fastapi import APIRouter
from sqlalchemy import select, text

from api.deps import CurrentUser, DbSession, require_role
from core.config import get_settings
from core.models import User

router = APIRouter(prefix="/system", tags=["system"])


def _hostport(url: str, default_port: int) -> tuple[str, int]:
    p = urlparse(url if "//" in url else "//" + url)
    return p.hostname or "127.0.0.1", p.port or default_port


def _tcp_ok(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


@router.get("/status")
async def system_status(session: DbSession, user: CurrentUser) -> list[dict]:
    """Status koneksi tiap layanan infrastruktur + provider AI (config)."""
    s = get_settings()
    out: list[dict] = []

    try:
        await session.execute(text("SELECT 1"))
        pg = "connected"
    except Exception:
        pg = "down"
    out.append({"name": "PostgreSQL", "kind": "Database", "status": pg, "detail": "sumber kebenaran"})

    checks = [
        ("Redis", "Queue / Cache", s.redis_url, 6379, "broker Celery + cache"),
        ("Qdrant", "Vector DB", s.qdrant_url, 6333, "pencarian semantik"),
        ("Neo4j", "Graph DB", s.neo4j_uri, 7687, "knowledge graph (Fase 3)"),
        ("MinIO", "Object Store", s.minio_endpoint, 9000, "raw data lake"),
    ]
    for name, kind, url, port, detail in checks:
        host, p = _hostport(url, port)
        ok = await asyncio.to_thread(_tcp_ok, host, p)
        out.append({"name": name, "kind": kind, "status": "connected" if ok else "down", "detail": detail})

    llm = s.llm_provider
    llm_key = True if llm == "stub" else bool(getattr(s, f"{llm}_api_key", ""))
    out.append({"name": f"LLM ({llm})", "kind": "AI Model", "status": "configured" if llm_key else "not_configured",
                "detail": "orkestrasi LangGraph (Tier R/F)"})
    out.append({"name": f"Embedding ({s.embed_provider})", "kind": "AI Model", "status": "configured",
                "detail": "vektorisasi komentar ke Qdrant"})
    out.append({"name": f"Classifier ({s.classifier_provider})", "kind": "AI Model", "status": "configured",
                "detail": "sentimen / emosi / intent"})
    return out


@router.get("/users", dependencies=[require_role("admin", "lead")])
async def system_users(session: DbSession) -> list[dict]:
    """Daftar pengguna terdaftar (admin/lead saja)."""
    rows = (await session.execute(select(User).order_by(User.created_at))).scalars().all()
    return [
        {"id": str(u.id), "name": u.name, "email": u.email, "role": u.role,
         "created_at": u.created_at.isoformat() if u.created_at else None}
        for u in rows
    ]

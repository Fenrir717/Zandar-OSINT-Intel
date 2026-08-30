from fastapi import APIRouter
from sqlalchemy import func, select

from api.deps import CurrentUser, DbSession
from core.models import Investigation, Project

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
async def list_projects(session: DbSession, user: CurrentUser) -> list[dict]:
    """Daftar project + jumlah investigasi per project (untuk halaman Projects)."""
    projects = (await session.execute(
        select(Project).order_by(Project.created_at.desc()).limit(100)
    )).scalars().all()
    counts = dict((await session.execute(
        select(Investigation.project_id, func.count()).group_by(Investigation.project_id)
    )).all())
    return [
        {
            "id": str(p.id), "name": p.name,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "investigation_count": counts.get(p.id, 0),
        }
        for p in projects
    ]

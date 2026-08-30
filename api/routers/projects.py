from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from api.deps import CurrentUser, DbSession
from core.models import AuditLog, Investigation, Project

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate, session: DbSession, user: CurrentUser) -> dict:
    p = Project(owner_id=user.id, name=body.name.strip())
    session.add(p)
    await session.flush()
    session.add(AuditLog(user_id=user.id, action="project.create", resource=f"project:{p.id}"))
    await session.commit()
    await session.refresh(p)
    return {
        "id": str(p.id), "name": p.name,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "investigation_count": 0,
    }


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

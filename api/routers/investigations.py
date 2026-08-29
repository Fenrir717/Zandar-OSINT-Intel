import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from api.deps import CurrentUser, DbSession
from api.schemas import InvestigationCreate, InvestigationOut, InvestigationUpdate
from core.models import AuditLog, Investigation, Project

router = APIRouter(prefix="/investigations", tags=["investigations"])


async def _default_project(session, user) -> Project:
    result = await session.execute(
        select(Project).where(Project.owner_id == user.id).order_by(Project.created_at).limit(1)
    )
    project = result.scalar_one_or_none()
    if project is None:
        project = Project(owner_id=user.id, name=f"Project {user.name}")
        session.add(project)
        await session.flush()
    return project


@router.get("", response_model=list[InvestigationOut])
async def list_investigations(session: DbSession, user: CurrentUser) -> list[Investigation]:
    result = await session.execute(
        select(Investigation).order_by(Investigation.created_at.desc()).limit(100)
    )
    return list(result.scalars().all())


@router.post("", response_model=InvestigationOut, status_code=status.HTTP_201_CREATED)
async def create_investigation(
    body: InvestigationCreate, session: DbSession, user: CurrentUser
) -> Investigation:
    if body.project_id is not None:
        project = await session.get(Project, body.project_id)
        if project is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project tidak ditemukan")
    else:
        project = await _default_project(session, user)

    inv = Investigation(
        project_id=project.id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        data_policy=body.data_policy,
        budget_cap_usd=body.budget_cap_usd,
        created_by=user.id,
    )
    session.add(inv)
    await session.flush()
    session.add(
        AuditLog(user_id=user.id, action="investigation.create", resource=f"investigation:{inv.id}")
    )
    await session.commit()
    await session.refresh(inv)
    return inv


@router.get("/{investigation_id}", response_model=InvestigationOut)
async def get_investigation(
    investigation_id: uuid.UUID, session: DbSession, user: CurrentUser
) -> Investigation:
    inv = await session.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigasi tidak ditemukan")
    return inv


@router.patch("/{investigation_id}", response_model=InvestigationOut)
async def update_investigation(
    investigation_id: uuid.UUID,
    body: InvestigationUpdate,
    session: DbSession,
    user: CurrentUser,
) -> Investigation:
    inv = await session.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigasi tidak ditemukan")

    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(inv, field, value)
    if changes:
        session.add(
            AuditLog(
                user_id=user.id,
                action="investigation.update",
                resource=f"investigation:{inv.id}",
                detail={"fields": sorted(changes.keys())},
            )
        )
    await session.commit()
    await session.refresh(inv)
    return inv

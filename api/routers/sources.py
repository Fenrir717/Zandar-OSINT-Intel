import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.deps import CurrentUser, DbSession, require_role
from core.models import AuditLog, Source

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceCreate(BaseModel):
    platform: str = Field(pattern="^(rss|youtube|reddit|telegram|forum)$")
    config: dict | None = None


class SourceOut(BaseModel):
    id: uuid.UUID
    platform: str
    status: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[SourceOut])
async def list_sources(session: DbSession, user: CurrentUser) -> list[Source]:
    result = await session.execute(select(Source).order_by(Source.created_at))
    return list(result.scalars().all())


@router.post(
    "",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_role("admin", "lead")],
)
async def create_source(body: SourceCreate, session: DbSession, user: CurrentUser) -> Source:
    src = Source(platform=body.platform, config=body.config)
    session.add(src)
    await session.flush()
    session.add(AuditLog(user_id=user.id, action="source.create", resource=f"source:{src.id}"))
    await session.commit()
    await session.refresh(src)
    return src


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[require_role("admin")])
async def delete_source(source_id: uuid.UUID, session: DbSession, user: CurrentUser) -> None:
    src = await session.get(Source, source_id)
    if src is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sumber tidak ditemukan")
    src.status = "disabled"  # soft-disable; koleksi lama tetap merujuk baris ini
    session.add(AuditLog(user_id=user.id, action="source.disable", resource=f"source:{src.id}"))
    await session.commit()

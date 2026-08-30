import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import CurrentUser, DbSession
from core.models import AuditLog, Collection, CollectionRun, Investigation, Source

router = APIRouter(prefix="/collections", tags=["collections"])


class CollectionCreate(BaseModel):
    investigation_id: uuid.UUID
    source_id: uuid.UUID | None = None
    platform: str | None = None  # alternatif source_id: Source dibuat/ditemukan otomatis
    query: dict
    schedule_cron: str | None = None


class CollectionOut(BaseModel):
    id: uuid.UUID
    investigation_id: uuid.UUID
    source_id: uuid.UUID
    query: dict
    schedule_cron: str | None
    last_run_at: datetime | None

    model_config = {"from_attributes": True}


class RunOut(BaseModel):
    id: uuid.UUID
    status: str
    items_collected: int
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[CollectionOut])
async def list_collections(
    session: DbSession, user: CurrentUser, investigation_id: uuid.UUID | None = None
) -> list[Collection]:
    stmt = select(Collection).order_by(Collection.created_at.desc()).limit(200)
    if investigation_id is not None:
        stmt = stmt.where(Collection.investigation_id == investigation_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=CollectionOut, status_code=status.HTTP_201_CREATED)
async def create_collection(
    body: CollectionCreate, session: DbSession, user: CurrentUser
) -> Collection:
    if await session.get(Investigation, body.investigation_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigasi tidak ditemukan")

    source_id = body.source_id
    if source_id is None:
        # Tanpa source_id eksplisit: temukan/buat Source berdasarkan platform.
        if not body.platform:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "source_id atau platform wajib diisi"
            )
        existing = (await session.execute(
            select(Source).where(Source.platform == body.platform).limit(1)
        )).scalar_one_or_none()
        if existing is not None:
            source_id = existing.id
        else:
            src = Source(platform=body.platform, config={})
            session.add(src)
            await session.flush()
            source_id = src.id
    elif await session.get(Source, source_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sumber tidak ditemukan")

    col = Collection(
        investigation_id=body.investigation_id,
        source_id=source_id,
        query=body.query,
        schedule_cron=body.schedule_cron,
    )
    session.add(col)
    await session.flush()
    session.add(AuditLog(user_id=user.id, action="collection.create", resource=f"collection:{col.id}"))
    await session.commit()
    await session.refresh(col)
    return col


@router.post("/{collection_id}/run", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(collection_id: uuid.UUID, session: DbSession, user: CurrentUser) -> CollectionRun:
    col = await session.get(Collection, collection_id)
    if col is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Koleksi tidak ditemukan")

    run = CollectionRun(collection_id=col.id, status="queued")
    session.add(run)
    await session.flush()
    session.add(
        AuditLog(user_id=user.id, action="collection.run", resource=f"collection_run:{run.id}")
    )
    await session.commit()
    await session.refresh(run)

    # Import lokal agar API tetap hidup walau stack worker belum terpasang
    from workers.tasks import collect_source

    collect_source.delay(str(col.id), str(run.id))
    return run


@router.get("/{collection_id}/runs", response_model=list[RunOut])
async def list_runs(
    collection_id: uuid.UUID, session: DbSession, user: CurrentUser
) -> list[CollectionRun]:
    result = await session.execute(
        select(CollectionRun)
        .where(CollectionRun.collection_id == collection_id)
        .order_by(CollectionRun.started_at.desc().nullslast())
        .limit(50)
    )
    return list(result.scalars().all())

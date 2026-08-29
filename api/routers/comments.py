import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from api.deps import CurrentUser, DbSession
from core.models import Comment

router = APIRouter(prefix="/comments", tags=["comments"])


class CommentOut(BaseModel):
    id: uuid.UUID
    investigation_id: uuid.UUID
    platform: str
    author_hash: str
    content: str
    lang: str | None
    url: str | None
    published_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("/search", response_model=list[CommentOut])
async def search_comments(
    session: DbSession,
    user: CurrentUser,
    investigation_id: uuid.UUID,
    q: str | None = None,
    platform: str | None = None,
    lang: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Comment]:
    """Pencarian keyword dasar (Fase 1). Fase 2: hybrid semantik via Qdrant."""
    stmt = (
        select(Comment)
        .where(Comment.investigation_id == investigation_id)
        .order_by(Comment.published_at.desc().nullslast())
        .limit(min(limit, 200))
        .offset(offset)
    )
    if q:
        stmt = stmt.where(Comment.content.ilike(f"%{q}%"))
    if platform:
        stmt = stmt.where(Comment.platform == platform)
    if lang:
        stmt = stmt.where(Comment.lang == lang)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/stats")
async def comment_stats(
    session: DbSession, user: CurrentUser, investigation_id: uuid.UUID
) -> dict:
    """Agregat ringkas untuk header Comment Explorer (Fase 1: hitungan dasar)."""
    total = await session.scalar(
        select(func.count()).select_from(Comment).where(Comment.investigation_id == investigation_id)
    )
    by_platform = await session.execute(
        select(Comment.platform, func.count())
        .where(Comment.investigation_id == investigation_id)
        .group_by(Comment.platform)
    )
    by_lang = await session.execute(
        select(Comment.lang, func.count())
        .where(Comment.investigation_id == investigation_id)
        .group_by(Comment.lang)
    )
    return {
        "total": total or 0,
        "by_platform": {p: c for p, c in by_platform.all()},
        "by_lang": {(lng or "?"): c for lng, c in by_lang.all()},
    }

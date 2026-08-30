import uuid
from datetime import datetime

from fastapi import APIRouter, status
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


class CommentHit(CommentOut):
    score: float


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


@router.post("/{investigation_id}/index", status_code=status.HTTP_202_ACCEPTED)
async def index_comments(
    investigation_id: uuid.UUID, session: DbSession, user: CurrentUser
) -> dict:
    """Picu embedding + indeks Qdrant untuk pencarian semantik."""
    from workers.tasks import embed_investigation

    task = embed_investigation.delay(str(investigation_id))
    return {"task_id": task.id, "status": "queued"}


@router.get("/semantic", response_model=list[CommentHit])
async def semantic_search(
    session: DbSession,
    user: CurrentUser,
    investigation_id: uuid.UUID,
    q: str,
    limit: int = 30,
    platform: str | None = None,
    lang: str | None = None,
) -> list[CommentHit]:
    """Pencarian semantik: embed query → Qdrant → join isi komentar dari PG."""
    from workers.embed import get_embedder
    from workers.vectorstore import search

    vec = get_embedder().embed([q])[0]
    hits = search(vec, str(investigation_id), limit=limit, platform=platform, lang=lang)
    if not hits:
        return []
    ids = [uuid.UUID(h["comment_id"]) for h in hits]
    score_by_id = {h["comment_id"]: h["score"] for h in hits}
    result = await session.execute(select(Comment).where(Comment.id.in_(ids)))
    by_id = {str(c.id): c for c in result.scalars().all()}
    out: list[CommentHit] = []
    for cid in [str(i) for i in ids]:
        c = by_id.get(cid)
        if c is None:
            continue
        out.append(CommentHit(
            id=c.id, investigation_id=c.investigation_id, platform=c.platform,
            author_hash=c.author_hash, content=c.content, lang=c.lang, url=c.url,
            published_at=c.published_at, score=round(score_by_id[cid], 4),
        ))
    return out


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

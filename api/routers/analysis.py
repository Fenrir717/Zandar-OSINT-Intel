import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy import Date, cast, func, select

from api.deps import CurrentUser, DbSession
from core.models import Analysis, AuditLog, Comment

router = APIRouter(prefix="/analysis", tags=["analysis"])


class AnalyzeAccepted(BaseModel):
    task_id: str
    status: str


@router.post(
    "/{investigation_id}/run", response_model=AnalyzeAccepted, status_code=status.HTTP_202_ACCEPTED
)
async def run_analysis(
    investigation_id: uuid.UUID, session: DbSession, user: CurrentUser
) -> AnalyzeAccepted:
    """Picu klasifikasi (Tier L) untuk komentar yang belum dianalisis."""
    session.add(
        AuditLog(user_id=user.id, action="analysis.run", resource=f"investigation:{investigation_id}")
    )
    await session.commit()

    from workers.tasks import classify_investigation

    from api.util import enqueue
    task = enqueue(classify_investigation, str(investigation_id))
    return AnalyzeAccepted(task_id=task.id, status="queued")


@router.get("/{investigation_id}/stats")
async def analysis_stats(
    investigation_id: uuid.UUID, session: DbSession, user: CurrentUser
) -> dict:
    """Agregat untuk halaman AI Analysis: cakupan, distribusi sentimen/emosi/intent,
    rerata & toksisitas, tren sentimen harian, tersangka bot."""
    inv = investigation_id

    total = await session.scalar(
        select(func.count()).select_from(Comment).where(Comment.investigation_id == inv)
    )
    analyzed = await session.scalar(
        select(func.count())
        .select_from(Analysis)
        .join(Comment, Comment.id == Analysis.comment_id)
        .where(Comment.investigation_id == inv)
    )

    async def dist(col):
        res = await session.execute(
            select(col, func.count())
            .join(Comment, Comment.id == Analysis.comment_id)
            .where(Comment.investigation_id == inv)
            .group_by(col)
        )
        return {(k or "?"): c for k, c in res.all()}

    avg_sent = await session.scalar(
        select(func.avg(Analysis.sentiment_score))
        .join(Comment, Comment.id == Analysis.comment_id)
        .where(Comment.investigation_id == inv)
    )
    bots = await session.scalar(
        select(func.count())
        .select_from(Analysis)
        .join(Comment, Comment.id == Analysis.comment_id)
        .where(Comment.investigation_id == inv, Analysis.is_bot_suspect.is_(True))
    )

    # Tren sentimen harian (rerata skor per hari publikasi)
    trend_res = await session.execute(
        select(
            cast(Comment.published_at, Date).label("day"),
            func.avg(Analysis.sentiment_score),
            func.count(),
        )
        .join(Analysis, Analysis.comment_id == Comment.id)
        .where(Comment.investigation_id == inv, Comment.published_at.is_not(None))
        .group_by("day")
        .order_by("day")
    )
    trend = [
        {"day": str(day), "avg": round(float(avg or 0), 3), "count": cnt}
        for day, avg, cnt in trend_res.all()
    ]

    return {
        "total": total or 0,
        "analyzed": analyzed or 0,
        "coverage": round((analyzed or 0) / total, 3) if total else 0,
        "sentiment": await dist(Analysis.sentiment),
        "emotion": await dist(Analysis.emotion),
        "intent": await dist(Analysis.intent),
        "avg_sentiment": round(float(avg_sent), 3) if avg_sent is not None else None,
        "bot_suspect": bots or 0,
        "sentiment_trend": trend,
    }

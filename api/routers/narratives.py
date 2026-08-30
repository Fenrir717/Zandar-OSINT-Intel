"""Graph C — narasi & skor risiko (PRD §7, §10).

POST /investigations/{id}/narratives/build → picu Graph C (Celery).
GET  /investigations/{id}/narratives       → daftar narasi + ABC+D + jumlah bukti.
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select

from api.deps import CurrentUser, DbSession
from core.models import (
    AuditLog,
    Comment,
    Investigation,
    Narrative,
    NarrativeAssessment,
    narrative_evidence,
)

router = APIRouter(tags=["narratives"])


class BuildRequest(BaseModel):
    threshold: float = 0.86  # cos-sim leader clustering (disetel untuk e5)
    min_size: int = 2        # cluster < ini dianggap noise, bukan narasi


class BuildAccepted(BaseModel):
    task_id: str
    status: str


@router.post(
    "/investigations/{investigation_id}/narratives/build",
    response_model=BuildAccepted, status_code=status.HTTP_202_ACCEPTED,
)
async def build_narratives(
    investigation_id: uuid.UUID, body: BuildRequest, session: DbSession, user: CurrentUser
) -> BuildAccepted:
    inv = await session.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigasi tidak ditemukan")

    session.add(AuditLog(
        user_id=user.id, action="narratives.build", resource=f"investigation:{investigation_id}"
    ))
    await session.commit()

    from workers.tasks import build_narratives as task

    t = task.delay(str(investigation_id), body.threshold, body.min_size)
    return BuildAccepted(task_id=t.id, status="queued")


@router.get("/investigations/{investigation_id}/narratives")
async def list_narratives(
    investigation_id: uuid.UUID, session: DbSession, user: CurrentUser
) -> list[dict]:
    """Narasi investigasi, terurut risiko tertinggi, dengan skor ABC+D & jumlah bukti."""
    nars = (await session.execute(
        select(Narrative).where(Narrative.investigation_id == investigation_id)
        .order_by(Narrative.risk_score.desc().nullslast())
    )).scalars().all()
    if not nars:
        return []

    ids = [n.id for n in nars]
    assess = {
        a.narrative_id: a for a in (await session.execute(
            select(NarrativeAssessment).where(NarrativeAssessment.narrative_id.in_(ids))
        )).scalars().all()
    }
    counts = dict((await session.execute(
        select(narrative_evidence.c.narrative_id, func.count())
        .where(narrative_evidence.c.narrative_id.in_(ids))
        .group_by(narrative_evidence.c.narrative_id)
    )).all())

    out = []
    for n in nars:
        a = assess.get(n.id)
        out.append({
            "id": str(n.id), "label": n.label, "summary": n.summary,
            "risk_score": n.risk_score, "risk_breakdown": n.risk_breakdown,
            "evidence_count": counts.get(n.id, 0),
            "first_seen": n.first_seen.isoformat() if n.first_seen else None,
            "last_seen": n.last_seen.isoformat() if n.last_seen else None,
            "assessment": None if a is None else {
                "actors": a.score_actors, "behavior": a.score_behavior,
                "content": a.score_content, "distribution": a.score_distribution,
                "authenticity": a.authenticity, "veracity": a.veracity,
                "quadrant": a.quadrant, "confidence": a.confidence,
            },
        })
    return out


@router.get("/narratives/{narrative_id}/evidence")
async def narrative_evidence_comments(
    narrative_id: uuid.UUID, session: DbSession, user: CurrentUser
) -> list[dict]:
    """Komentar/artikel bukti sebuah narasi + LINK SUMBER asli (provenance/keterlacakan)."""
    rows = (await session.execute(
        select(
            Comment.id, Comment.platform, Comment.author_hash, Comment.content,
            Comment.url, Comment.lang, Comment.published_at,
        )
        .join(narrative_evidence, narrative_evidence.c.comment_id == Comment.id)
        .where(narrative_evidence.c.narrative_id == narrative_id)
        .order_by(Comment.published_at.desc().nullslast())
        .limit(50)
    )).all()
    return [
        {"id": str(r[0]), "platform": r[1], "author_hash": r[2], "content": r[3],
         "url": r[4], "lang": r[5], "published_at": r[6].isoformat() if r[6] else None}
        for r in rows
    ]

"""Verifikasi Klaim (Graph E, fase 5) — verdict DRAF ber-basis bukti.

POST /investigations/{id}/claims/verify → jalankan Graph E (sinkron) → simpan.
GET  /investigations/{id}/claims        → daftar klaim + verdict + sumber.

Build sinkron: aksi eksplisit analis; Graph E punya fallback konservatif
('insufficient') sehingga selalu selesai walau LLM/sumber resmi gagal.
Verdict berstatus DRAFT — penilaian AI, menunggu tinjauan analis.
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from api.deps import CurrentUser, DbSession
from core.models import AuditLog, Claim, ClaimVerdict, Investigation, Narrative

router = APIRouter(tags=["claims"])


@router.post(
    "/investigations/{investigation_id}/claims/verify", status_code=status.HTTP_201_CREATED
)
async def verify_claims(
    investigation_id: uuid.UUID, session: DbSession, user: CurrentUser
) -> dict:
    inv = await session.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigasi tidak ditemukan")
    session.add(AuditLog(
        user_id=user.id, action="claims.verify", resource=f"investigation:{investigation_id}"
    ))
    await session.commit()

    from graphs.runner import run_verify

    result = await run_verify(session, inv)
    if result.get("claims", 0) == 0 and result.get("note"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, result["note"])
    return result


@router.get("/investigations/{investigation_id}/claims")
async def list_claims(
    investigation_id: uuid.UUID, session: DbSession, user: CurrentUser
) -> list[dict]:
    rows = (await session.execute(
        select(Claim, ClaimVerdict, Narrative.label)
        .outerjoin(ClaimVerdict, ClaimVerdict.claim_id == Claim.id)
        .outerjoin(Narrative, Narrative.id == Claim.narrative_id)
        .where(Claim.investigation_id == investigation_id)
        .order_by(Claim.created_at.desc())
    )).all()
    out: list[dict] = []
    for claim, verdict, nar_label in rows:
        refs = (verdict.evidence_refs if verdict else None) or {}
        out.append({
            "id": str(claim.id),
            "narrative_id": str(claim.narrative_id) if claim.narrative_id else None,
            "narrative_label": nar_label,
            "claim": claim.text_normalized,
            "check_worthy": claim.check_worthy,
            "verdict": verdict.verdict if verdict else None,
            "confidence": float(verdict.confidence) if verdict and verdict.confidence is not None else None,
            "veracity": refs.get("veracity"),
            "rationale": refs.get("rationale"),
            "authoritative": refs.get("authoritative", []),
            "review_status": verdict.review_status if verdict else None,
            "created_at": claim.created_at.isoformat() if claim.created_at else None,
        })
    return out

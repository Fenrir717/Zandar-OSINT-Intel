"""Reports (Graph D, fase 4) — laporan intelijen BER-SITASI.

POST /investigations/{id}/reports/build → jalankan Graph D (sinkron) → simpan.
GET  /investigations/{id}/reports        → daftar laporan (metadata).
GET  /reports/{id}                        → isi laporan (dari MinIO) + metadata.

Build dijalankan sinkron: aksi eksplisit analis, Graph D punya fallback per
bagian sehingga selalu selesai walau LLM gagal (beberapa detik).
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import CurrentUser, DbSession
from core.models import AuditLog, Investigation, Report

router = APIRouter(tags=["reports"])


class ReportMeta(BaseModel):
    id: str
    title: str
    status: str
    classification: str
    created_at: str | None
    generated_by_run: str | None


@router.post(
    "/investigations/{investigation_id}/reports/build", status_code=status.HTTP_201_CREATED
)
async def build_report(
    investigation_id: uuid.UUID, session: DbSession, user: CurrentUser
) -> dict:
    inv = await session.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigasi tidak ditemukan")
    session.add(AuditLog(
        user_id=user.id, action="report.build", resource=f"investigation:{investigation_id}"
    ))
    await session.commit()

    from graphs.runner import run_report

    result = await run_report(session, inv)
    if result.get("report_id") is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            result.get("note", "Belum ada narasi untuk dilaporkan."),
        )
    return result


@router.get("/investigations/{investigation_id}/reports", response_model=list[ReportMeta])
async def list_reports(
    investigation_id: uuid.UUID, session: DbSession, user: CurrentUser
) -> list[ReportMeta]:
    rows = (await session.execute(
        select(Report)
        .where(Report.investigation_id == investigation_id)
        .order_by(Report.created_at.desc())
    )).scalars().all()
    return [
        ReportMeta(
            id=str(r.id), title=r.title, status=r.status, classification=r.classification,
            created_at=r.created_at.isoformat() if r.created_at else None,
            generated_by_run=str(r.generated_by_run) if r.generated_by_run else None,
        )
        for r in rows
    ]


@router.get("/reports/{report_id}")
async def get_report(report_id: uuid.UUID, session: DbSession, user: CurrentUser) -> dict:
    r = await session.get(Report, report_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Laporan tidak ditemukan")
    content = None
    if r.content_ref:
        from workers.raw_lake import get_json
        try:
            content = get_json(r.content_ref)
        except Exception:  # noqa: BLE001 — objek hilang/MinIO mati → metadata saja
            content = None
    return {
        "id": str(r.id), "title": r.title, "status": r.status,
        "classification": r.classification,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "content": content,
    }

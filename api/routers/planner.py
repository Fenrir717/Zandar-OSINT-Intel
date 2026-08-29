import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import CurrentUser, DbSession
from core.models import AgentRun, AuditLog, Investigation

router = APIRouter(tags=["planner"])


class PlanRequest(BaseModel):
    query: str


class ApproveRequest(BaseModel):
    edited_sources: list[dict] | None = None


@router.post("/investigations/{investigation_id}/plan", status_code=status.HTTP_201_CREATED)
async def plan(
    investigation_id: uuid.UUID, body: PlanRequest, session: DbSession, user: CurrentUser
) -> dict:
    """Jalankan Graph A sampai interrupt approval; kembalikan rencana koleksi."""
    inv = await session.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigasi tidak ditemukan")

    from graphs.runner import start_plan

    result = await start_plan(session, inv, body.query)
    session.add(AuditLog(user_id=user.id, action="planner.plan", resource=f"agent_run:{result['agent_run_id']}"))
    await session.commit()
    return result


@router.post("/agent-runs/{run_id}/approve")
async def approve(
    run_id: uuid.UUID, body: ApproveRequest, session: DbSession, user: CurrentUser
) -> dict:
    """Resume Graph A dengan approval → dispatch koleksi."""
    return await _resume(session, user, run_id, "approve", body.edited_sources)


@router.post("/agent-runs/{run_id}/reject")
async def reject(run_id: uuid.UUID, session: DbSession, user: CurrentUser) -> dict:
    """Resume Graph A dengan penolakan → graph berakhir tanpa koleksi."""
    return await _resume(session, user, run_id, "reject", None)


@router.get("/agent-runs")
async def list_runs(
    session: DbSession, user: CurrentUser, investigation_id: uuid.UUID | None = None
) -> list[dict]:
    stmt = select(AgentRun).order_by(AgentRun.started_at.desc()).limit(100)
    if investigation_id is not None:
        stmt = stmt.where(AgentRun.investigation_id == investigation_id)
    res = await session.execute(stmt)
    return [
        {
            "id": str(r.id), "graph_name": r.graph_name, "status": r.status,
            "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
            "cost_usd": float(r.cost_usd), "started_at": r.started_at.isoformat() if r.started_at else None,
            "ended_at": r.ended_at.isoformat() if r.ended_at else None,
        }
        for r in res.scalars().all()
    ]


async def _resume(session, user, run_id: uuid.UUID, decision: str, edited: list[dict] | None) -> dict:
    run = await session.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent run tidak ditemukan")
    if run.status != "awaiting_approval":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Run tidak menunggu approval (status: {run.status})")

    from graphs.runner import resume_plan

    result = await resume_plan(session, str(run_id), decision, edited)
    session.add(AuditLog(user_id=user.id, action=f"planner.{decision}", resource=f"agent_run:{run_id}"))
    await session.commit()
    return result

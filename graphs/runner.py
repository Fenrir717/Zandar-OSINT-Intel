"""Runner Graph A: menjalankan graph (sync) dari kode API (async), mengelola
interrupt/resume, dan melakukan tulis DB async (agent_runs, collections, dispatch).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import AgentRun, Collection, CollectionRun, Investigation, Source
from graphs.planner import planner_graph


def _interrupt_payload(result: dict) -> dict | None:
    """Ambil nilai interrupt dari hasil invoke LangGraph (bila graph tersuspensi)."""
    intr = result.get("__interrupt__")
    if not intr:
        return None
    first = intr[0]
    return getattr(first, "value", first)


async def start_plan(session: AsyncSession, inv: Investigation, query: str) -> dict:
    run = AgentRun(investigation_id=inv.id, graph_name="planner", status="running")
    session.add(run)
    await session.flush()
    run_id = str(run.id)

    graph = planner_graph()
    config = {"configurable": {"thread_id": run_id}}
    init = {
        "investigation_id": str(inv.id),
        "query": query,
        "data_policy": inv.data_policy,
        "budget_cap_usd": float(inv.budget_cap_usd) if inv.budget_cap_usd is not None else None,
        "usage": {},
    }
    result = await asyncio.to_thread(graph.invoke, init, config)
    plan = _interrupt_payload(result)

    usage = result.get("usage", {})
    run.tokens_in = usage.get("tokens_in", 0)
    run.tokens_out = usage.get("tokens_out", 0)
    run.status = "awaiting_approval"
    await session.commit()

    return {"agent_run_id": run_id, "status": "awaiting_approval", "plan": plan}


async def resume_plan(
    session: AsyncSession, run_id: str, decision: str, edited_sources: list[dict] | None
) -> dict:
    run = await session.get(AgentRun, uuid.UUID(run_id))
    if run is None:
        raise ValueError("agent_run tidak ditemukan")

    graph = planner_graph()
    config = {"configurable": {"thread_id": run_id}}
    result = await asyncio.to_thread(
        graph.invoke,
        Command(resume={"decision": decision, "edited_sources": edited_sources}),
        config,
    )

    dispatched: list[str] = []
    if decision == "approve":
        dispatched = await _dispatch_sources(session, run.investigation_id, result.get("sources", []))

    usage = result.get("usage", {})
    run.tokens_in = usage.get("tokens_in", run.tokens_in)
    run.tokens_out = usage.get("tokens_out", run.tokens_out)
    run.status = "done" if decision == "approve" else "rejected"
    run.ended_at = datetime.now(UTC)
    await session.commit()

    return {"agent_run_id": run_id, "decision": decision, "dispatched_collections": dispatched}


async def _get_or_create_source(session: AsyncSession, platform: str) -> Source:
    res = await session.execute(
        select(Source).where(Source.platform == platform, Source.status == "active").limit(1)
    )
    src = res.scalar_one_or_none()
    if src is None:
        src = Source(platform=platform, config={})
        session.add(src)
        await session.flush()
    return src


async def _dispatch_sources(
    session: AsyncSession, investigation_id: uuid.UUID, sources: list[dict]
) -> list[str]:
    """Buat Collection + CollectionRun(queued) per sumber dan enqueue collect_source."""
    from workers.tasks import collect_source

    created: list[str] = []
    for s in sources:
        platform = s.get("platform")
        if platform is None:
            continue
        src = await _get_or_create_source(session, platform)
        col = Collection(investigation_id=investigation_id, source_id=src.id, query=s.get("query", {}))
        session.add(col)
        await session.flush()
        run = CollectionRun(collection_id=col.id, status="queued")
        session.add(run)
        await session.flush()
        collect_source.delay(str(col.id), str(run.id))
        created.append(str(col.id))
    return created


# Reset graph singleton (dipakai test agar checkpointer bersih)
def reset_graph() -> None:
    import graphs.planner as p

    p._graph = None


__all__: list[str] = ["start_plan", "resume_plan", "reset_graph"]

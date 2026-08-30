"""Runner Graph A: menjalankan graph (sync) dari kode API (async), mengelola
interrupt/resume, dan melakukan tulis DB async (agent_runs, collections, dispatch).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from langgraph.types import Command
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import (
    AgentRun,
    Analysis,
    Collection,
    CollectionRun,
    Comment,
    Investigation,
    Narrative,
    NarrativeAssessment,
    Source,
    narrative_evidence,
)
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


# ---------------------------------------------------------------- Graph C (analysis)

async def run_analysis(
    session: AsyncSession, inv: Investigation, threshold: float, min_size: int
) -> dict:
    """Jalankan Graph C: cluster komentar (Qdrant) → narasi → skor risiko → simpan.

    Idempoten: narasi lama investigasi dihapus lalu ditulis ulang (re-run aman)."""
    import asyncio as _asyncio

    from graphs.narrator import narrator_graph
    from workers.vectorstore import fetch_vectors

    inv_pk = inv.id
    inv_id = str(inv.id)

    run = AgentRun(investigation_id=inv_pk, graph_name="analysis", status="running")
    session.add(run)
    await session.flush()
    run_id = run.id

    # Meta komentar + analisis (untuk skoring risiko) dari Postgres
    res = await session.execute(
        select(
            Comment.id, Comment.author_hash, Comment.platform, Comment.published_at,
            Comment.content, Analysis.toxicity, Analysis.sentiment,
        )
        .outerjoin(Analysis, Analysis.comment_id == Comment.id)
        .where(Comment.investigation_id == inv_pk)
    )
    rows = res.all()
    # PENTING: tutup transaksi baca SEBELUM graph (47 LLM call bisa >60s → jangan
    # biarkan tx menganga; idle_in_transaction_session_timeout akan memutus koneksi).
    await session.commit()

    vectors = await _asyncio.to_thread(fetch_vectors, inv_id)  # Qdrant, tanpa tx PG
    # Gabung: hanya komentar yang punya vektor (sudah di-embed). Urut stabil.
    items = [
        {
            "comment_id": str(r[0]), "vector": vectors[str(r[0])],
            "author_hash": r[1], "platform": r[2],
            "published_at": r[3].isoformat() if r[3] else None,
            "content": r[4], "toxicity": r[5], "sentiment": r[6],
        }
        for r in rows if str(r[0]) in vectors
    ]
    items.sort(key=lambda it: (it["published_at"] or "", it["comment_id"]))

    if not items:
        run = await session.get(AgentRun, run_id)
        run.status = "done"
        run.ended_at = datetime.now(UTC)
        await session.commit()
        return {"agent_run_id": str(run_id), "embedded": 0, "narratives": 0,
                "note": "Belum ada komentar ter-embed. Jalankan indexing dulu."}

    graph = narrator_graph()
    result = await _asyncio.to_thread(
        graph.invoke, {"investigation_id": inv_id, "items": items, "threshold": threshold, "min_size": min_size}, {}
    )  # LONG (LLM) — tanpa transaksi PG terbuka
    narratives = result.get("narratives", [])

    # Tulis ulang narasi (cascade hapus evidence + assessment lama) — transaksi baru
    await session.execute(delete(Narrative).where(Narrative.investigation_id == inv_pk))
    for n in narratives:
        row = Narrative(
            investigation_id=inv.id, label=n["label"], summary=n.get("summary"),
            risk_score=n["risk_score"], risk_breakdown=n["risk_breakdown"],
            first_seen=_parse_iso(n.get("first_seen")), last_seen=_parse_iso(n.get("last_seen")),
        )
        session.add(row)
        await session.flush()
        member_ids = [items[i]["comment_id"] for i in n["member_idx"]]
        await session.execute(
            insert(narrative_evidence),
            [{"narrative_id": row.id, "comment_id": uuid.UUID(cid)} for cid in member_ids],
        )
        a = n["assessment"]
        session.add(NarrativeAssessment(
            narrative_id=row.id, score_actors=a["score_actors"], score_behavior=a["score_behavior"],
            score_content=a["score_content"], score_distribution=a["score_distribution"],
            authenticity=a["authenticity"], veracity=a["veracity"], quadrant=a["quadrant"],
            confidence=a["confidence"], assessed_at=datetime.now(UTC),
        ))

    usage = result.get("usage", {})
    run = await session.get(AgentRun, run_id)
    run.tokens_in = usage.get("tokens_in", 0)
    run.tokens_out = usage.get("tokens_out", 0)
    run.status = "done"
    run.ended_at = datetime.now(UTC)
    await session.commit()

    return {
        "agent_run_id": str(run_id), "embedded": len(items), "narratives": len(narratives),
        "top": [{"label": n["label"], "risk_score": n["risk_score"], "size": n["size"]}
                for n in narratives[:5]],
    }


def _parse_iso(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None


# Reset graph singleton (dipakai test agar checkpointer bersih)
def reset_graph() -> None:
    import graphs.narrator as n
    import graphs.planner as p

    p._graph = None
    n._graph = None


__all__: list[str] = ["start_plan", "resume_plan", "run_analysis", "reset_graph"]

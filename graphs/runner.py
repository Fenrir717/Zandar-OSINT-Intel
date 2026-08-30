"""Runner Graph A: menjalankan graph (sync) dari kode API (async), mengelola
interrupt/resume, dan melakukan tulis DB async (agent_runs, collections, dispatch).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from langgraph.types import Command
from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.events import publish_agent_event
from core.models import (
    AgentRun,
    Analysis,
    Claim,
    ClaimVerdict,
    Collection,
    CollectionRun,
    Comment,
    Investigation,
    Narrative,
    NarrativeAssessment,
    Report,
    Source,
    narrative_evidence,
)
from graphs.planner import planner_graph

_NODE_LABEL = {  # pesan ramah untuk feed live Agent Monitor
    "cluster": "mengelompokkan komentar",
    "label_narratives": "melabeli narasi",
    "score_risk": "menilai risiko",
}


def _stream_graph(graph, init: dict, run_id: str, inv_id: str) -> dict:
    """Jalankan graph via stream (sinkron, dalam thread), publikasikan tiap node
    selesai ke bus event, kembalikan state akhir terakumulasi."""
    final: dict = {}
    for step in graph.stream(init, {}, stream_mode="updates"):
        for node, delta in step.items():
            if isinstance(delta, dict):
                final.update(delta)
            if node == "cluster":
                detail = f"{len(final.get('clusters', []))} klaster"
            elif node == "label_narratives":
                detail = f"{len(final.get('narratives', []))} narasi dilabeli"
            else:
                detail = _NODE_LABEL.get(node, node)
            publish_agent_event({
                "type": "run", "id": run_id, "investigation_id": inv_id,
                "graph": "analysis", "status": "running", "node": node, "detail": detail,
            })
    return final


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

    publish_agent_event({
        "type": "run", "id": run_id, "investigation_id": str(inv.id), "graph": "planner",
        "status": "awaiting_approval", "node": "human_approval", "detail": "menunggu approval analis",
    })
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

    publish_agent_event({
        "type": "run", "id": run_id, "investigation_id": str(run.investigation_id), "graph": "planner",
        "status": run.status, "node": decision,
        "detail": f"{len(dispatched)} koleksi didispatch" if decision == "approve" else "ditolak",
    })
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

    publish_agent_event({
        "type": "run", "id": str(run_id), "investigation_id": inv_id, "graph": "analysis",
        "status": "running", "node": "start", "detail": f"{len(items)} komentar ter-embed",
    })
    graph = narrator_graph()
    init = {"investigation_id": inv_id, "items": items, "threshold": threshold, "min_size": min_size}
    result = await _asyncio.to_thread(_stream_graph, graph, init, str(run_id), inv_id)  # LONG (LLM), tanpa tx PG
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

    publish_agent_event({
        "type": "run", "id": str(run_id), "investigation_id": inv_id, "graph": "analysis",
        "status": "done", "node": "done", "detail": f"{len(narratives)} narasi",
        "narratives": len(narratives), "tokens_in": run.tokens_in, "tokens_out": run.tokens_out,
    })
    return {
        "agent_run_id": str(run_id), "embedded": len(items), "narratives": len(narratives),
        "top": [{"label": n["label"], "risk_score": n["risk_score"], "size": n["size"]}
                for n in narratives[:5]],
    }


# ---------------------------------------------------------------- Graph D (report)

async def run_report(session: AsyncSession, inv: Investigation) -> dict:
    """Jalankan Graph D: narasi + bukti → laporan ber-sitasi → simpan (MinIO + Report).

    Tiap build = snapshot Report baru (histori dipertahankan)."""
    import asyncio as _asyncio

    from graphs.report import reporter_graph
    from workers.raw_lake import put_report

    inv_pk = inv.id
    inv_id = str(inv.id)

    run = AgentRun(investigation_id=inv_pk, graph_name="report", status="running")
    session.add(run)
    await session.flush()
    run_id = run.id

    # Narasi teratas (berisiko) + bukti wakil (dengan URL sumber) dari Postgres.
    nrows = (await session.execute(
        select(Narrative.id, Narrative.label, Narrative.summary,
               Narrative.risk_score, Narrative.risk_breakdown)
        .where(Narrative.investigation_id == inv_pk)
        .order_by(Narrative.risk_score.desc().nullslast())
        .limit(12)
    )).all()
    nar_ids = [r[0] for r in nrows]
    evidence_by_nar: dict = {nid: [] for nid in nar_ids}
    if nar_ids:
        erows = (await session.execute(
            select(narrative_evidence.c.narrative_id, Comment.content, Comment.url,
                   Comment.platform, Comment.published_at)
            .join(Comment, Comment.id == narrative_evidence.c.comment_id)
            .where(narrative_evidence.c.narrative_id.in_(nar_ids))
            .order_by(Comment.published_at.desc().nullslast())
        )).all()
        for nid, content, url, platform, published_at in erows:
            lst = evidence_by_nar.get(nid)
            if lst is not None and len(lst) < 3:
                lst.append({"content": content, "url": url, "platform": platform,
                            "published_at": published_at.isoformat() if published_at else None})
    narratives = [
        {"label": r[1], "summary": r[2],
         "risk_score": float(r[3]) if r[3] is not None else None,
         "risk_breakdown": r[4] or {}, "evidence": evidence_by_nar.get(r[0], [])}
        for r in nrows
    ]

    total = await session.scalar(
        select(func.count()).select_from(Comment).where(Comment.investigation_id == inv_pk))
    analyzed = await session.scalar(
        select(func.count()).select_from(Analysis)
        .join(Comment, Comment.id == Analysis.comment_id)
        .where(Comment.investigation_id == inv_pk))
    stats = {"total": total or 0, "analyzed": analyzed or 0,
             "coverage": round((analyzed or 0) / total, 3) if total else 0}

    await session.commit()  # tutup tx sebelum LLM (write_section bisa lama)

    if not narratives:
        run = await session.get(AgentRun, run_id)
        run.status = "done"
        run.ended_at = datetime.now(UTC)
        await session.commit()
        return {"agent_run_id": str(run_id), "report_id": None,
                "note": "Belum ada narasi. Jalankan analisis (Graph C) dulu."}

    title = f"Laporan Intelijen — {inv.title}"
    publish_agent_event({
        "type": "run", "id": str(run_id), "investigation_id": inv_id, "graph": "report",
        "status": "running", "node": "start", "detail": f"{len(narratives)} narasi",
    })
    graph = reporter_graph()
    init = {"investigation_id": inv_id, "title": title, "narratives": narratives, "stats": stats}
    result = await _asyncio.to_thread(graph.invoke, init, {})  # LONG (LLM), tanpa tx PG
    doc = result.get("report", {})

    report = Report(investigation_id=inv_pk, title=title, status="final", generated_by_run=run_id)
    session.add(report)
    await session.flush()
    ref = await _asyncio.to_thread(put_report, inv_id, str(report.id), doc)
    report.content_ref = ref

    usage = result.get("usage", {})
    run = await session.get(AgentRun, run_id)
    run.tokens_in = usage.get("tokens_in", 0)
    run.tokens_out = usage.get("tokens_out", 0)
    run.status = "done"
    run.ended_at = datetime.now(UTC)
    await session.commit()

    publish_agent_event({
        "type": "run", "id": str(run_id), "investigation_id": inv_id, "graph": "report",
        "status": "done", "node": "done",
        "detail": f"laporan · {doc.get('meta', {}).get('cited_sources', 0)} sitasi",
        "tokens_in": run.tokens_in, "tokens_out": run.tokens_out,
    })
    return {
        "agent_run_id": str(run_id), "report_id": str(report.id),
        "cited_sources": doc.get("meta", {}).get("cited_sources", 0),
        "sections": len(doc.get("sections", [])),
    }


# ---------------------------------------------------------------- Graph E (veracity)

def _keywords(text: str, k: int = 6) -> list[str]:
    """Kata kunci ekstraktif (untuk pencarian ground-truth BPS/BMKG)."""
    from graphs.llm import _STOP, _WORD

    freq: dict[str, int] = {}
    for w in _WORD.findall((text or "").lower()):
        if w not in _STOP and len(w) > 3:
            freq[w] = freq.get(w, 0) + 1
    return sorted(freq, key=lambda w: (-freq[w], w))[:k]


async def run_verify(session: AsyncSession, inv: Investigation) -> dict:
    """Jalankan Graph E: klaim narasi → verifikasi vs bukti internal + ground-truth
    resmi (BPS/BMKG) → verdict DRAF (AVeriTeC) + veracity + kuadran.

    Idempoten: klaim lama investigasi dihapus lalu ditulis ulang."""
    import asyncio as _asyncio

    from graphs.verify import verifier_graph

    inv_pk = inv.id
    inv_id = str(inv.id)

    run = AgentRun(investigation_id=inv_pk, graph_name="veracity", status="running")
    session.add(run)
    await session.flush()
    run_id = run.id

    nrows = (await session.execute(
        select(Narrative.id, Narrative.label, Narrative.summary, NarrativeAssessment.authenticity)
        .outerjoin(NarrativeAssessment, NarrativeAssessment.narrative_id == Narrative.id)
        .where(Narrative.investigation_id == inv_pk)
        .order_by(Narrative.risk_score.desc().nullslast())
        .limit(8)
    )).all()
    nar_ids = [r[0] for r in nrows]
    evidence_by_nar: dict = {nid: [] for nid in nar_ids}
    if nar_ids:
        erows = (await session.execute(
            select(narrative_evidence.c.narrative_id, Comment.content, Comment.url,
                   Comment.platform, Comment.published_at)
            .join(Comment, Comment.id == narrative_evidence.c.comment_id)
            .where(narrative_evidence.c.narrative_id.in_(nar_ids))
            .order_by(Comment.published_at.desc().nullslast())
        )).all()
        for nid, content, url, platform, published_at in erows:
            lst = evidence_by_nar.get(nid)
            if lst is not None and len(lst) < 4:
                lst.append({"content": content, "url": url, "platform": platform,
                            "published_at": published_at.isoformat() if published_at else None})
    narratives = [
        {"id": str(r[0]), "label": r[1], "summary": r[2],
         "authenticity": float(r[3]) if r[3] is not None else None,
         "keywords": _keywords(f"{r[1] or ''} {r[2] or ''}"),
         "evidence": evidence_by_nar.get(r[0], [])}
        for r in nrows
    ]

    await session.commit()  # tutup tx sebelum IO adapter + LLM

    if not narratives:
        run = await session.get(AgentRun, run_id)
        run.status = "done"
        run.ended_at = datetime.now(UTC)
        await session.commit()
        return {"agent_run_id": str(run_id), "claims": 0,
                "note": "Belum ada narasi. Jalankan analisis (Graph C) dulu."}

    publish_agent_event({
        "type": "run", "id": str(run_id), "investigation_id": inv_id, "graph": "veracity",
        "status": "running", "node": "retrieve_evidence", "detail": "menarik ground-truth resmi",
    })
    graph = verifier_graph()
    init = {"investigation_id": inv_id, "narratives": narratives}
    result = await _asyncio.to_thread(graph.invoke, init, {})  # LONG (IO+LLM), tanpa tx PG
    results = result.get("results", [])

    # Tulis ulang klaim + verdict (idempoten) dan update veracity/kuadran narasi.
    await session.execute(delete(Claim).where(Claim.investigation_id == inv_pk))
    used_auth = 0
    for res in results:
        nid = uuid.UUID(res["narrative_id"]) if res.get("narrative_id") else None
        claim = Claim(narrative_id=nid, investigation_id=inv_pk,
                      text_normalized=res["claim"], check_worthy=res["check_worthy"])
        session.add(claim)
        await session.flush()
        session.add(ClaimVerdict(
            claim_id=claim.id, verdict=res["verdict"], confidence=res.get("confidence"),
            evidence_refs={"veracity": res.get("veracity"), "rationale": res.get("rationale"),
                           "authoritative": res.get("authoritative", [])},
            review_status="draft", model_version="graph-e/llm-F",
        ))
        if res.get("authoritative"):
            used_auth += 1
        if nid is not None:
            await session.execute(
                NarrativeAssessment.__table__.update()
                .where(NarrativeAssessment.narrative_id == nid)
                .values(veracity=res.get("veracity"), quadrant=res.get("quadrant"))
            )

    usage = result.get("usage", {})
    run = await session.get(AgentRun, run_id)
    run.tokens_in = usage.get("tokens_in", 0)
    run.tokens_out = usage.get("tokens_out", 0)
    run.status = "done"
    run.ended_at = datetime.now(UTC)
    await session.commit()

    publish_agent_event({
        "type": "run", "id": str(run_id), "investigation_id": inv_id, "graph": "veracity",
        "status": "done", "node": "done",
        "detail": f"{len(results)} klaim · {used_auth} pakai sumber resmi",
        "tokens_in": run.tokens_in, "tokens_out": run.tokens_out,
    })
    return {
        "agent_run_id": str(run_id), "claims": len(results),
        "with_authoritative": used_auth,
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


__all__: list[str] = [
    "start_plan", "resume_plan", "run_analysis", "run_report", "run_verify", "reset_graph",
]

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Date, cast, func, select

from api.deps import CurrentUser, DbSession
from core.models import Analysis, AuditLog, Comment, Investigation, Narrative

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
    avg_conf = await session.scalar(
        select(func.avg(Analysis.confidence))
        .join(Comment, Comment.id == Analysis.comment_id)
        .where(Comment.investigation_id == inv)
    )
    sarcasm = await session.scalar(
        select(func.count())
        .select_from(Analysis)
        .join(Comment, Comment.id == Analysis.comment_id)
        .where(Comment.investigation_id == inv, Analysis.is_sarcasm.is_(True))
    )
    low_conf = await session.scalar(
        select(func.count())
        .select_from(Analysis)
        .join(Comment, Comment.id == Analysis.comment_id)
        .where(Comment.investigation_id == inv, Analysis.confidence < 0.7)
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
        "avg_confidence": round(float(avg_conf), 3) if avg_conf is not None else None,
        "sarcasm": sarcasm or 0,
        "low_confidence": low_conf or 0,
        "sentiment_trend": trend,
    }


@router.get("/{investigation_id}/entities")
async def entity_sentiment(
    investigation_id: uuid.UUID, user: CurrentUser, limit: int = 20
) -> list[dict]:
    """Sentimen per-target-entitas (Tier 2) — dari knowledge graph Neo4j.

    Butuh graph sudah dibangun (build_graph) SETELAH klasifikasi agar tiap entitas
    membawa agregat sentimen komentar yang menyebutnya."""
    import asyncio

    from core import graph

    try:
        return await asyncio.to_thread(graph.read_entities, str(investigation_id), limit)
    except Exception:  # noqa: BLE001 — Neo4j mati / graph belum dibangun → kosong
        return []


# ---------------------------------------------------------------- AI Chat (Tier 3)

class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[dict] = []  # [{role: 'user'|'assistant', content}] — opsional


_CHAT_SYSTEM = (
    "Anda asisten intelijen untuk platform analisis sentimen & forensik narasi. "
    "Jawab pertanyaan analis HANYA berdasarkan DATA investigasi yang diberikan. "
    "WAJIB Bahasa Indonesia, ringkas, dan ACTIONABLE — beri wawasan/rekomendasi bila "
    "relevan. Rujuk entitas/narasi/angka SPESIFIK dari data. Bila data tak cukup untuk "
    "menjawab, katakan terus terang — JANGAN mengarang angka atau fakta. "
    "Balas HANYA JSON {\"answer\": \"...\"}."
)


async def _chat_context(session: DbSession, inv: uuid.UUID, title: str) -> str:
    lines = [f"Judul investigasi: {title}"]
    total = await session.scalar(
        select(func.count()).select_from(Comment).where(Comment.investigation_id == inv))
    analyzed = await session.scalar(
        select(func.count()).select_from(Analysis)
        .join(Comment, Comment.id == Analysis.comment_id)
        .where(Comment.investigation_id == inv))
    lines.append(f"Komentar: {total or 0} total, {analyzed or 0} dianalisis.")

    async def _dist(col, limit: int | None = None):
        stmt = (select(col, func.count())
                .join(Comment, Comment.id == Analysis.comment_id)
                .where(Comment.investigation_id == inv).group_by(col)
                .order_by(func.count().desc()))
        if limit:
            stmt = stmt.limit(limit)
        return (await session.execute(stmt)).all()

    srows = await _dist(Analysis.sentiment)
    if srows:
        lines.append("Sentimen: " + ", ".join(f"{k or '?'}={c}" for k, c in srows))
    erows = await _dist(Analysis.emotion, 5)
    if erows:
        lines.append("Emosi teratas: " + ", ".join(f"{k or '?'}={c}" for k, c in erows))
    irows = await _dist(Analysis.intent, 5)
    if irows:
        lines.append("Intent teratas: " + ", ".join(f"{k or '?'}={c}" for k, c in irows))

    nrows = (await session.execute(
        select(Narrative.label, Narrative.summary, Narrative.risk_score)
        .where(Narrative.investigation_id == inv)
        .order_by(Narrative.risk_score.desc().nullslast()).limit(8))).all()
    if nrows:
        lines.append("Narasi berisiko (label | risiko | ringkasan):")
        for lbl, summ, risk in nrows:
            r = round(float(risk), 2) if risk is not None else "-"
            lines.append(f"- {lbl} | {r} | {(summ or '')[:120]}")

    import asyncio

    from core import graph
    try:
        ents = await asyncio.to_thread(graph.read_entities, str(inv), 12)
    except Exception:  # noqa: BLE001
        ents = []
    if ents:
        lines.append("Entitas & sentimen (nama | tipe | sebut | pos/netral/neg | skor | emosi):")
        for e in ents:
            lines.append(
                f"- {e['name']} | {e['type']} | {e['mentions']} | "
                f"{e['pos']}/{e['neu']}/{e['neg']} | {e['sent_score']} | {e['emotion'] or '-'}")
    return "\n".join(lines)


@router.post("/{investigation_id}/chat")
async def chat(
    investigation_id: uuid.UUID, body: ChatRequest, session: DbSession, user: CurrentUser
) -> dict:
    """Asisten AI: jawab pertanyaan analis berbasis DATA investigasi (grounded)."""
    inv = await session.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigasi tidak ditemukan")
    context = await _chat_context(session, investigation_id, inv.title)

    import asyncio

    def _ask() -> str:
        from graphs.llm import get_llm

        hist = ""
        for m in (body.history or [])[-4:]:
            who = "Analis" if m.get("role") == "user" else "Asisten"
            hist += f"{who}: {str(m.get('content', ''))[:400]}\n"
        user_msg = (
            f"DATA INVESTIGASI:\n{context}\n\n"
            + (f"RIWAYAT PERCAKAPAN:\n{hist}\n" if hist else "")
            + f"PERTANYAAN: {body.question}"
        )
        try:
            # Tier F lebih andal untuk chat (model reasoning gratis kerap balas answer kosong).
            r = get_llm().call_json("F", _CHAT_SYSTEM, user_msg, hint={"node": "chat"})
            ans = str((r.data or {}).get("answer") or "").strip()
            return ans or "Maaf, saya tidak menemukan jawaban dari data yang tersedia."
        except Exception:  # noqa: BLE001 — LLM gagal → pesan jujur
            return "Maaf, asisten sedang tidak tersedia (LLM gagal). Coba lagi sebentar."

    answer = await asyncio.to_thread(_ask)
    return {"answer": answer}

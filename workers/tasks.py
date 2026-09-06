"""Task Celery — layer koleksi (Fase 1).

Alur collect_source (idempoten):
  CollectionRun(running) → adapter.collect() → raw ke MinIO → enrichment
  deterministik → INSERT comments (ON CONFLICT DO NOTHING via kunci
  (platform, external_id)) → CollectionRun(done, items_collected).
"""

import asyncio
import uuid
from datetime import UTC, datetime

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.db import worker_session
from core.events import publish_agent_event
from core.models import Analysis, Collection, CollectionRun, Comment, Investigation, Source
from workers.adapters import ADAPTERS, AdapterNotConfigured, CostGuardRejected
from workers.celery_app import celery_app
from workers.classify import get_classifier
from workers.classify.cache import get_cached, set_cached
from workers.classify.preprocess import preprocess_for_classify
from workers.classify.refine import refine_low_confidence
from workers.enrichment import enrich
from workers.raw_lake import ensure_bucket, put_raw


@celery_app.task
def ping() -> str:
    """Smoke test worker: celery -A workers.celery_app call workers.tasks.ping"""
    return "pong"


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def collect_source(self, collection_id: str, run_id: str) -> dict:
    return asyncio.run(_collect(collection_id, run_id))


def _review_rating(raw: dict | None) -> int | None:
    """Ambil bintang 1-5 dari payload review (raw.score) bila valid; else None."""
    v = (raw or {}).get("score")
    return v if isinstance(v, int) and 1 <= v <= 5 else None


async def _collect(collection_id: str, run_id: str) -> dict:
    async with worker_session() as session:
        run = await session.get(CollectionRun, uuid.UUID(run_id))
        collection = await session.get(Collection, uuid.UUID(collection_id))
        if run is None or collection is None:
            return {"status": "not_found"}
        source = await session.get(Source, collection.source_id)

        run.status = "running"
        run.started_at = datetime.now(UTC)
        await session.commit()

        adapter_cls = ADAPTERS.get(source.platform)
        if adapter_cls is None:
            run.status = "failed"
            run.error = f"Adapter tidak dikenal: {source.platform}"
            run.finished_at = datetime.now(UTC)
            await session.commit()
            return {"status": "failed", "error": run.error}

        adapter = adapter_cls(config=source.config or {})
        raw_lake_ok = True
        try:
            ensure_bucket()
        except Exception:  # MinIO mati tidak boleh menghentikan koleksi — raw_ref=None
            raw_lake_ok = False

        inserted = 0
        try:
            for item in adapter.collect(collection.query or {}):
                raw_ref = None
                if raw_lake_ok:
                    try:
                        raw_ref = put_raw(item.platform, run_id, item.external_id, item.raw)
                    except Exception:
                        raw_lake_ok = False

                fields = enrich(item.platform, item.author, item.content)
                stmt = (
                    pg_insert(Comment)
                    .values(
                        id=uuid.uuid4(),
                        collection_run_id=run.id,
                        investigation_id=collection.investigation_id,
                        platform=item.platform,
                        external_id=item.external_id,
                        url=item.url,
                        rating=_review_rating(item.raw),  # bintang review (playstore/appstore)
                        raw_ref=raw_ref,
                        published_at=item.published_at,
                        **fields,
                    )
                    .on_conflict_do_nothing(index_elements=["platform", "external_id"])
                )
                result = await session.execute(stmt)
                if result.rowcount:
                    inserted += 1
                if inserted % 200 == 0:
                    await session.commit()

            run.status = "done"
        except CostGuardRejected as exc:
            # Sumber metered dipanggil tanpa persetujuan biaya — bukan bug, tapi
            # penolakan yang disengaja; jangan retry.
            run.status = "failed"
            run.error = f"Cost guard: {exc}"
        except (AdapterNotConfigured, NotImplementedError) as exc:
            run.status = "failed"
            run.error = str(exc)
        except Exception as exc:  # kegagalan adapter dicatat, tidak meledak tanpa jejak
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {exc}"

        run.items_collected = inserted
        run.finished_at = datetime.now(UTC)
        collection.last_run_at = run.finished_at
        await session.commit()
        return {"status": run.status, "items_collected": inserted}


@celery_app.task(bind=True)
def classify_investigation(
    self, investigation_id: str, batch_size: int = 200, reclassify: bool = False
) -> dict:
    """Klasifikasi komentar investigasi → upsert `analyses`.
    reclassify=False (default): hanya komentar tanpa analisis (idempoten).
    reclassify=True: proses ulang SEMUA (mis. setelah ganti CLASSIFIER_PROVIDER)."""
    return asyncio.run(_classify(investigation_id, batch_size, reclassify))


async def _classify(investigation_id: str, batch_size: int, reclassify: bool = False) -> dict:
    clf = get_classifier()
    analyzed = 0
    cache_hits = 0
    inv = uuid.UUID(investigation_id)
    seen: set = set()  # id yang sudah diproses — cegah loop tak henti (upsert tak kurangi kandidat)

    while True:
        # Fase 1 — baca batch (transaksi PENDEK, langsung ditutup).
        async with worker_session() as session:
            stmt = select(Comment.id, Comment.content).where(Comment.investigation_id == inv)
            if not reclassify:
                stmt = stmt.outerjoin(Analysis, Analysis.comment_id == Comment.id).where(
                    Analysis.comment_id.is_(None)
                )
            if seen:
                stmt = stmt.where(Comment.id.notin_(seen))
            rows = (await session.execute(stmt.limit(batch_size))).all()
        if not rows:
            break

        # Fase 2 — klasifikasi + refine TANPA koneksi DB terbuka. refine sarkasme
        # (LLM per-item) bisa makan menit; menahan koneksi di sini memicu
        # idle_in_transaction_session_timeout → "connection closed" saat menulis.
        raw_texts = [content for _, content in rows]
        pre_texts = [preprocess_for_classify(t) for t in raw_texts]  # slang/emoji → baku

        # Cache Redis: teks identik (spam/template) tak dianalisis ulang. reclassify
        # memaksa segar (agar perubahan model/pipeline terpakai) tapi tetap refresh cache.
        cached = [None] * len(pre_texts) if reclassify else get_cached(pre_texts, clf.version)
        miss = [i for i, c in enumerate(cached) if c is None]
        labels: list = list(cached)
        if miss:
            fresh = clf.classify([pre_texts[i] for i in miss])
            refine_low_confidence([raw_texts[i] for i in miss], fresh)  # sarkasme, low-conf saja
            set_cached([pre_texts[i] for i in miss], fresh, clf.version)
            for j, i in enumerate(miss):
                labels[i] = fresh[j]
        cache_hits += len(pre_texts) - len(miss)

        # Fase 3 — tulis hasil (transaksi PENDEK, koneksi segar).
        now = datetime.now(UTC)
        async with worker_session() as session:
            for (cid, _), lab in zip(rows, labels, strict=True):
                values = dict(
                    comment_id=cid, sentiment=lab.sentiment, sentiment_score=lab.sentiment_score,
                    emotion=lab.emotion, intent=lab.intent, toxicity=lab.toxicity,
                    confidence=lab.confidence, is_sarcasm=lab.is_sarcasm,
                    model_version=lab.model_version, analyzed_at=now,
                )
                ins = pg_insert(Analysis).values(**values)
                if reclassify:
                    stmt2 = ins.on_conflict_do_update(
                        index_elements=["comment_id"],
                        set_={k: values[k] for k in values if k != "comment_id"},
                    )
                else:
                    stmt2 = ins.on_conflict_do_nothing(index_elements=["comment_id"])
                await session.execute(stmt2)
            await session.commit()

        for cid, _ in rows:
            seen.add(cid)
        analyzed += len(rows)

    return {"investigation_id": investigation_id, "analyzed": analyzed,
            "cache_hits": cache_hits, "model": clf.version}


@celery_app.task(bind=True)
def embed_investigation(self, investigation_id: str, batch_size: int = 100) -> dict:
    """Embed komentar investigasi → indeks Qdrant (pencarian semantik)."""
    return asyncio.run(_embed(investigation_id, batch_size))


async def _embed(investigation_id: str, batch_size: int) -> dict:
    from workers.embed import get_embedder
    from workers.vectorstore import ensure_collection, upsert

    emb = get_embedder()
    ensure_collection(emb.dim)
    indexed = 0
    async with worker_session() as session:
        result = await session.execute(
            select(Comment.id, Comment.content, Comment.platform, Comment.lang, Comment.published_at)
            .where(Comment.investigation_id == uuid.UUID(investigation_id))
        )
        rows = result.all()
    for i in range(0, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        vectors = emb.embed([r[1] for r in chunk])
        payloads = [
            {
                "comment_id": str(r[0]), "investigation_id": investigation_id,
                "platform": r[2], "lang": r[3],
                "published_at": r[4].isoformat() if r[4] else None,
            }
            for r in chunk
        ]
        indexed += upsert(vectors, payloads)
    return {"investigation_id": investigation_id, "indexed": indexed, "model": emb.version, "dim": emb.dim}


@celery_app.task(bind=True)
def build_narratives(self, investigation_id: str, threshold: float = 0.86, min_size: int = 2) -> dict:
    """Graph C: cluster komentar ter-embed → narasi + skor risiko (butuh embedding dulu)."""
    return asyncio.run(_build_narratives(investigation_id, threshold, min_size))


async def _build_narratives(investigation_id: str, threshold: float, min_size: int) -> dict:
    from graphs.runner import run_analysis

    async with worker_session() as session:
        inv = await session.get(Investigation, uuid.UUID(investigation_id))
        if inv is None:
            return {"status": "not_found"}
        return await run_analysis(session, inv, threshold, min_size)


@celery_app.task(bind=True)
def build_graph(self, investigation_id: str, batch_size: int = 500) -> dict:
    """Fase 3: NER komentar → knowledge graph Neo4j (entitas + ko-okurensi)."""
    return asyncio.run(_build_graph(investigation_id, batch_size))


async def _build_graph(investigation_id: str, batch_size: int) -> dict:
    async with worker_session() as session:
        rows = (await session.execute(
            select(Comment.content, Analysis.sentiment, Analysis.sentiment_score, Analysis.emotion)
            .outerjoin(Analysis, Analysis.comment_id == Comment.id)
            .where(Comment.investigation_id == uuid.UUID(investigation_id))
        )).all()
    texts = [r[0] for r in rows]
    if not texts:
        return {"investigation_id": investigation_id, "nodes": 0, "edges": 0, "note": "belum ada komentar"}
    # Sentimen per komentar (sejajar texts) → ditautkan ke entitas (Tier 2).
    sentiments = [
        {"sentiment": r[1], "score": float(r[2]) if r[2] is not None else None, "emotion": r[3]}
        for r in rows
    ]
    res = await asyncio.to_thread(_ner_and_write, investigation_id, texts, sentiments)
    return {"investigation_id": investigation_id, "comments": len(texts), **res}


def _ner_and_write(inv_id: str, texts: list[str], sentiments: list[dict] | None = None) -> dict:
    """NER + tulis Neo4j — sinkron, dijalankan dalam thread (CPU-bound + driver sync)."""
    from core import graph
    from workers.ner import get_ner

    ents = get_ner().extract(texts)
    return graph.write_graph(inv_id, ents, sentiments)


# ---------------------------------------------------------------- Autonomous loop (Commander)

@celery_app.task(bind=True)
def run_scan_pipeline(self, investigation_id: str) -> dict:
    """Autonomous loop: setelah SEMUA koleksi scan selesai, jalankan rantai analisis
    penuh — classify → embed → narasi (Graph C) → knowledge graph + sentimen per-target.

    Dipicu sebagai callback chord dari dispatch koleksi (lihat graphs.runner). Tiap
    tahap memancarkan event 'scan' ke bus agar UI Scan menampilkan progres langsung.
    Kegagalan satu tahap dicatat tapi tak menghentikan tahap lain yang masih mungkin
    (mis. graph tetap dicoba walau narasi gagal)."""
    return asyncio.run(_scan_pipeline(investigation_id))


async def _scan_pipeline(investigation_id: str) -> dict:
    def emit(node: str, detail: str, status: str = "running") -> None:
        publish_agent_event({
            "type": "run", "id": f"scan-{investigation_id}", "investigation_id": investigation_id,
            "graph": "scan", "status": status, "node": node, "detail": detail,
        })

    out: dict = {"investigation_id": investigation_id, "stages": {}}
    stages = (
        ("classify", "mengklasifikasi komentar (sentimen · emosi · sarkasme)",
         lambda: _classify(investigation_id, 200, False)),
        ("embed", "meng-embed komentar untuk klasterisasi narasi",
         lambda: _embed(investigation_id, 100)),
        ("narratives", "mengelompokkan & melabeli narasi (Graph C)",
         lambda: _build_narratives(investigation_id, 0.86, 2)),
        ("graph", "membangun knowledge graph + sentimen per-target",
         lambda: _build_graph(investigation_id, 500)),
    )
    for node, detail, fn in stages:
        emit(node, detail)
        try:
            out["stages"][node] = await fn()
        except Exception as exc:  # tahap gagal dicatat, pipeline lanjut
            out["stages"][node] = {"error": f"{type(exc).__name__}: {exc}"}
            emit(node, f"gagal: {type(exc).__name__}", status="failed")

    nar = out["stages"].get("narratives", {})
    detail = f"selesai · {nar.get('narratives', 0)} narasi" if isinstance(nar, dict) else "selesai"
    emit("done", detail, status="done")
    return out


def _is_due(cron_expr: str, last_run_at: datetime | None, now: datetime) -> bool:
    """True bila tick cron terakhir (<= now) belum tercakup last_run_at.

    Contoh: cron '0 */6 * * *' (tiap 6 jam). Bila fire terjadwal terakhir jam 12:00
    dan last_run_at jam 06:30, maka jatuh tempo. Bila last_run_at jam 12:05, belum.
    """
    if not croniter.is_valid(cron_expr):
        return False
    prev_fire = croniter(cron_expr, now).get_prev(datetime)  # tick terjadwal terakhir <= now
    if last_run_at is None:
        return True
    if last_run_at.tzinfo is None:
        last_run_at = last_run_at.replace(tzinfo=UTC)
    return last_run_at < prev_fire


@celery_app.task
def dispatch_due_collections() -> dict:
    """Beat memanggil ini tiap 60 dtk: enqueue collect_source untuk collection
    yang schedule_cron-nya jatuh tempo. Jadwal ada di DB agar bisa diubah via API."""
    return asyncio.run(_dispatch_due())


async def _dispatch_due() -> dict:
    now = datetime.now(UTC)
    dispatched: list[str] = []
    async with worker_session() as session:
        result = await session.execute(
            select(Collection).where(Collection.schedule_cron.is_not(None))
        )
        collections = list(result.scalars().all())

        for col in collections:
            if not _is_due(col.schedule_cron, col.last_run_at, now):
                continue
            # Lewati bila sudah ada run antre/berjalan untuk collection ini (anti dobel-dispatch)
            active = await session.execute(
                select(CollectionRun.id)
                .where(
                    CollectionRun.collection_id == col.id,
                    CollectionRun.status.in_(("queued", "running")),
                )
                .limit(1)
            )
            if active.scalar_one_or_none() is not None:
                continue

            run = CollectionRun(collection_id=col.id, status="queued")
            session.add(run)
            col.last_run_at = now  # tandai tick cron ini tertangani (cegah re-dispatch)
            await session.flush()
            collect_source.delay(str(col.id), str(run.id))
            dispatched.append(str(col.id))

        await session.commit()
    return {"checked": len(collections), "dispatched": dispatched}

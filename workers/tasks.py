"""Task Celery — layer koleksi (Fase 1).

Alur collect_source (idempoten):
  CollectionRun(running) → adapter.collect() → raw ke MinIO → enrichment
  deterministik → INSERT comments (ON CONFLICT DO NOTHING via kunci
  (platform, external_id)) → CollectionRun(done, items_collected).
"""

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.db import SessionLocal
from core.models import Collection, CollectionRun, Comment, Source
from workers.adapters import ADAPTERS, AdapterNotConfigured, CostGuardRejected
from workers.celery_app import celery_app
from workers.enrichment import enrich
from workers.raw_lake import ensure_bucket, put_raw


@celery_app.task
def ping() -> str:
    """Smoke test worker: celery -A workers.celery_app call workers.tasks.ping"""
    return "pong"


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def collect_source(self, collection_id: str, run_id: str) -> dict:
    return asyncio.run(_collect(collection_id, run_id))


async def _collect(collection_id: str, run_id: str) -> dict:
    async with SessionLocal() as session:
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


async def _latest_run_ids() -> list[str]:
    """Dipakai beat (Fase 1 lanjutan) — placeholder agar import bersih."""
    async with SessionLocal() as session:
        result = await session.execute(select(CollectionRun.id).limit(1))
        return [str(r) for r in result.scalars().all()]

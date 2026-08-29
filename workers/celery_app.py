"""Celery app — layer koleksi & enrichment (PRD §6: "Celery bekerja").

Jalankan worker:
    celery -A workers.celery_app worker --loglevel=info --pool=solo   # --pool=solo untuk Windows
Jalankan beat (jadwal cron koleksi, Fase 1):
    celery -A workers.celery_app beat --loglevel=info
"""

from celery import Celery

from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "zandar",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # job koleksi berdurasi panjang — jangan serakah prefetch
    task_default_queue="default",
    task_routes={
        "workers.tasks.collect_source": {"queue": "collect"},
    },
)

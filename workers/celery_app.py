"""Celery app — layer koleksi & enrichment (PRD §6: "Celery bekerja").

Jalankan worker (WINDOWS: WAJIB --pool=threads — solo/prefork menggantung di
Windows + Python 3.14; threads menghindari billiard/multiprocessing):
    celery -A workers.celery_app worker --loglevel=info --pool=threads -Q default,collect

Jalankan beat (memicu koleksi terjadwal berbasis schedule_cron di DB):
    celery -A workers.celery_app beat --loglevel=info
"""

from celery import Celery
from celery.schedules import crontab  # noqa: F401 — tersedia bila ingin jadwal statis

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
    # Beat: tiap 60 detik, dispatcher memeriksa collection mana yang jatuh tempo
    # menurut schedule_cron-nya dan meng-enqueue collect_source. Jadwal disimpan
    # di DB (bukan di config), jadi analis bisa mengubahnya via API tanpa restart.
    beat_schedule={
        "dispatch-due-collections": {
            "task": "workers.tasks.dispatch_due_collections",
            "schedule": 60.0,
        },
        # Early Warning proaktif: sapu investigasi aktif tiap 15 menit → deteksi
        # lonjakan negatif → alert Telegram/email otomatis (dedup 3 jam).
        "early-warning-sweep": {
            "task": "workers.tasks.dispatch_early_warning",
            "schedule": 900.0,
        },
    },
)

#!/usr/bin/env bash
# Entrypoint container app Zandar. Satu image, tiga peran (api|worker|beat) via arg pertama.
# api: migrasi DB (alembic) → seed admin idempoten → uvicorn. worker/beat: Celery.
set -euo pipefail

role="${1:-api}"
echo "[entrypoint] role=${role}"

run_migrations() {
  echo "[entrypoint] alembic upgrade head ..."
  for i in 1 2 3 4 5; do
    if alembic upgrade head; then
      echo "[entrypoint] migrasi OK"
      return 0
    fi
    echo "[entrypoint] migrasi gagal (percobaan ${i}/5) — tunggu 3s"
    sleep 3
  done
  echo "[entrypoint] migrasi TETAP gagal setelah 5 percobaan" >&2
  return 1
}

case "${role}" in
  api)
    run_migrations
    echo "[entrypoint] seed admin (idempoten; aktif bila ADMIN_EMAIL & ADMIN_PASSWORD diset)"
    python scripts/create_admin.py || echo "[entrypoint] seed admin dilewati/gagal (non-fatal)"
    echo "[entrypoint] uvicorn api.main:app :8010"
    exec uvicorn api.main:app --host 0.0.0.0 --port 8010
    ;;
  worker)
    # --pool=threads: konsisten dgn perilaku dev (adapter pakai asyncio in-thread).
    exec celery -A workers.celery_app worker \
      --loglevel=info --pool=threads -Q default,collect \
      --without-mingle --without-gossip --without-heartbeat
    ;;
  beat)
    exec celery -A workers.celery_app beat --loglevel=info
    ;;
  *)
    # peran tak dikenal → jalankan apa adanya (debug: docker compose run app bash)
    exec "$@"
    ;;
esac

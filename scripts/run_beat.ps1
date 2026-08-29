# Jalankan Celery beat (Windows) — memicu koleksi terjadwal (schedule_cron di DB)
# tiap 60 detik via task dispatch_due_collections. Jalankan bersama worker.
# Pakai: powershell -File scripts\run_beat.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
.\.venv\Scripts\python.exe -m celery -A workers.celery_app beat --loglevel=info

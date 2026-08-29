# Jalankan Celery worker (Windows). WAJIB --pool=threads: solo/prefork
# menggantung di Windows + Python 3.14 (billiard/multiprocessing).
# Pakai: powershell -File scripts\run_worker.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
.\.venv\Scripts\python.exe -m celery -A workers.celery_app worker `
    --loglevel=info --pool=threads -Q default,collect `
    --without-mingle --without-gossip --without-heartbeat

# Jalankan Celery worker (Windows). WAJIB --pool=threads: solo/prefork
# menggantung di Windows + Python 3.14 (billiard/multiprocessing).
# Pakai: powershell -File scripts\run_worker.ps1
#
# Otomatis pakai .venv311 (Python 3.11 + torch CUDA, GPU) bila ada — IndoBERT +
# embed jalan di GPU (~22x lebih cepat). Fallback ke .venv (CPU) bila belum migrasi.
# Lihat docs/gpu-migration.md.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = if (Test-Path ".\.venv311\Scripts\python.exe") { ".\.venv311\Scripts\python.exe" } else { ".\.venv\Scripts\python.exe" }
Write-Host "worker via: $py" -ForegroundColor Cyan
& $py -m celery -A workers.celery_app worker `
    --loglevel=info --pool=threads -Q default,collect `
    --without-mingle --without-gossip --without-heartbeat

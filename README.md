# Zandar OSINT Intel

Platform OSINT analisis sentimen & forensik narasi berbahasa Indonesia.
Backend FastAPI · orkestrasi LangGraph · Qdrant (vector) · Neo4j (knowledge graph) ·
PostgreSQL (sumber kebenaran) · Celery/Redis (koleksi) · MinIO (raw data lake).

Prinsip arsitektur (PRD §6): **LangGraph berpikir, Celery bekerja, model lokal
mengklasifikasi, database mengingat.**

## Status: Fase 0 — Fondasi

| Fase | Isi | Status |
|------|-----|--------|
| 0 | Monorepo, docker-compose, FastAPI + JWT/RBAC, Alembic, CI | ✅ ini |
| 1 | 11 adapter koleksi, enrichment deterministik, worker+beat, Comment Explorer | ✅ |
| 2 | IndoBERT/Flash-LLM, Qdrant, LangGraph Graph A & C | ⬜ |
| 3 | Neo4j, deteksi CIB, forensik narasi (kuadran) | ⬜ |
| 4 | Graph D (laporan ber-sitasi), hardening | ⬜ |
| 5 | Graph E (verifikasi klaim) | ⬜ |

## Adapter koleksi (11 platform, 3 tier akses)

Adapter berbagi satu kontrak (`collect(query) → RawItem[]`) dan mendeklarasikan
metadata akses yang dibaca UI, planner, dan estimasi biaya — cek via
`GET /api/v1/sources/adapters`.

| Tier | Platform | Jalur akses | Catatan |
|------|----------|-------------|---------|
| **free** | `rss` | Feed RSS/Atom | Ringkasan dari feed |
| | `news` | GDELT DOC 2.0 → trafilatura | Gratis tanpa key, 65 bahasa; teks penuh |
| | `blog` | Autodiscovery feed → trafilatura | Teks penuh tiap tulisan |
| | `website` | sitemap.xml / URL → trafilatura | Crawl terbatas, hormat robots.txt |
| | `forum` | Discourse JSON publik | Non-Discourse pakai `website` |
| | `github` | REST API resmi | 5rb req/jam; search 30 req/menit |
| | `youtube` | Data API v3 | Kuota 10rb unit/hari |
| | `reddit` | JSON publik | Komersial butuh kontrak Reddit |
| | `telegram` | MTProto (menyusul) | Butuh sesi Telethon |
| **metered** | `x` | API v2 pay-per-use | ~$0,005/post; **cost guard wajib** |
| **vendor** | `tiktok` | Penyedia data berkontrak | Tak ada akses komersial resmi |

`news`, `blog`, `website` (dan fallback `rss`) berbagi modul ekstraksi
[`web_extract.py`](workers/adapters/web_extract.py) — mereka berbeda hanya pada
cara **menemukan** URL, bukan cara mengambil teks.

## Struktur

```
core/      # config, db, security, model SQLAlchemy (ERD PRD §8.1 + §10.6)
api/       # FastAPI — auth JWT + RBAC, investigations CRUD
workers/   # Celery — job koleksi & enrichment (stub di Fase 0)
graphs/    # LangGraph A/C/D/E (mulai Fase 2 — lihat graphs/README.md)
web/       # frontend React (mulai Fase 1)
alembic/   # migrasi database
scripts/   # utilitas (create_admin)
tests/     # smoke test (tanpa servis eksternal)
```

## Quickstart

Prasyarat: Python 3.11+, Docker Desktop.

```bash
# 1. Konfigurasi
cp .env.example .env        # lalu ganti JWT_SECRET

# 2. Infrastruktur (PostgreSQL, Redis, Qdrant, Neo4j, MinIO)
docker compose up -d

# 3. Dependensi Python
python -m venv .venv
.venv\Scripts\activate      # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -e ".[dev]"

# 4. Migrasi skema
alembic upgrade head

# 5. User admin pertama
python scripts/create_admin.py --email admin@zandar.local --password gantipassword

# 6. Jalankan API
uvicorn api.main:app --reload
```

Frontend (React SPA, di-build ke `web/dist`, disajikan API): **http://localhost:8000/**
Dev frontend: `cd web && npm install && npm run dev` (Vite :5173, proxy ke API).
Swagger UI: http://localhost:8000/docs

Servis (port terisolasi, lihat Catatan Windows): Neo4j http://localhost:7475 ·
MinIO Console http://localhost:9003 · Qdrant http://localhost:6335/dashboard

### Worker & scheduler (koleksi terjadwal)

Worker menjalankan job koleksi; beat memicu koleksi ber-`schedule_cron` (tiap 60 dtk
mengecek collection yang jatuh tempo). Di Windows pakai skrip berikut (sudah memakai
`--pool=threads` yang wajib):

```bash
powershell -File scripts/run_worker.ps1
powershell -File scripts/run_beat.ps1
```

Non-Windows setara:

```bash
celery -A workers.celery_app worker --loglevel=info -Q default,collect
celery -A workers.celery_app beat --loglevel=info
```

## Uji gate Fase 0

Login → buat investigasi → baris masuk DB:

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login -d "username=admin@zandar.local&password=gantipassword" -H "Content-Type: application/x-www-form-urlencoded"
```

Pakai `access_token` dari respons:

```bash
curl -s -X POST http://localhost:8000/api/v1/investigations -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" -d "{\"title\": \"Investigasi pertama\", \"priority\": \"high\"}"
```

Test & lint lokal:

```bash
pytest -q
ruff check .
```

## Catatan Windows (penting)

Divalidasi di Windows 11 + Docker Desktop. Beberapa penyesuaian yang sudah diterapkan:

- **Port digeser ke rentang terisolasi** (`5433/6380/6335-6336/7475/7688/9002-9003`)
  agar tidak bentrok dengan stack lain di WSL/host. Lihat `docker-compose.yml`.
- **Gunakan `127.0.0.1`, bukan `localhost`, di `.env`.** Pada Windows, `localhost`
  dapat resolve ke IPv6/WSL lebih dulu dan membuat koneksi MinIO hang ~21 detik
  per permintaan. `.env.example` sudah memakai `127.0.0.1`.
- **Celery worker native belum stabil di Windows + Python 3.14** (consumer solo-pool
  menggantung sebelum `ready`). Pipeline koleksi sudah terbukti benar bila dipicu
  langsung; untuk worker terjadwal, jalankan worker di dalam WSL atau Python 3.12.
  Ini item terbuka Fase 1, bukan cacat pipeline.

## Klasifikasi lokal IndoBERT (opsional, Fase 2)

Baseline `lexicon` (default) jalan tanpa dependensi. Untuk classifier kontekstual
IndoBERT (menangkap nuansa yang leksikon lewatkan, mis. "ekonomi rapuh"→negatif):

```bash
pip install -e ".[ml]"          # torch + transformers (~2.5GB)
# lalu di .env:
CLASSIFIER_PROVIDER=indobert
```

Provider `indobert` bersifat HIBRIDA: RoBERTa fine-tuned Indonesia untuk sentimen +
leksikon untuk emosi/intent/toksisitas. Model diunduh sekali dari HuggingFace (~500MB).

**CPU vs GPU:** `pip install torch` default di Windows = CPU-only (~22 komentar/dtk;
100rb komentar ≈ 75 menit). Untuk GPU (RTX 3050, ~5-10× lebih cepat), pasang build CUDA:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121 --force-reinstall
```

Bandingkan provider pada data nyata (preview bake-off):

```bash
python scripts/classifier_compare.py --a lexicon --b indobert --limit 300
```

## Observability (opsional)

```bash
docker compose --profile observability up -d   # Langfuse di http://localhost:3001
```

## Catatan kepatuhan

Identitas penulis komentar disimpan sebagai `author_hash` (pseudonim) sejak ingestion;
`data_policy=local_only` pada investigasi memaksa klasifikasi model lokal — konten tidak
dikirim ke API pihak ketiga. Detail: PRD §12–13.

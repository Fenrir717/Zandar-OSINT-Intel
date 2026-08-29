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
| 1 | Adapter koleksi (RSS/YouTube/Reddit/Telegram), enrichment deterministik | ⬜ |
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

Swagger UI: http://localhost:8000/docs · Neo4j Browser: http://localhost:7474 ·
MinIO Console: http://localhost:9001 · Qdrant: http://localhost:6333/dashboard

Worker Celery (opsional di Fase 0):

```bash
celery -A workers.celery_app worker --loglevel=info --pool=solo
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

## Observability (opsional)

```bash
docker compose --profile observability up -d   # Langfuse di http://localhost:3001
```

## Catatan kepatuhan

Identitas penulis komentar disimpan sebagai `author_hash` (pseudonim) sejak ingestion;
`data_policy=local_only` pada investigasi memaksa klasifikasi model lokal — konten tidak
dikirim ke API pihak ketiga. Detail: PRD §12–13.

# Bake-off Classifier — Lexicon vs IndoBERT vs Flash (LLM)

Evaluasi akurasi (macro-F1) tiga provider klasifikasi pada **gold set berlabel manusia**,
untuk memutuskan jalur produksi (PRD §7.4). Semua provider dinilai pada **sampel yang
sama** per task (seed tetap 42) agar adil.

Reproduksi:

```bash
.venv/Scripts/python.exe scripts/bakeoff.py --limit 150
# lebih besar (tanpa flash, cepat): scripts/bakeoff.py --providers lexicon indobert --limit 0
```

## Gold set

| Task | Sumber (berlabel manusia) | Label |
|---|---|---|
| Sentimen | NusaX-Senti (IndoNLP), split `test` | neg / neu / pos |
| Emosi | IndoNLU EmoT (tweet ID), split `test` | anger / fear / joy / trust / sadness |
| Toksisitas | Hate-speech ID (Ibrohim & Budi 2019), kolom `HS` | hate / clean |

Cache lokal di `data/gold/`. Bake-off berjalan pada **sampel 150/task** (dibatasi karena
Flash memakai panggilan LLM yang lambat/berbiaya); IndoBERT & Lexicon bisa dievaluasi
pada gold penuh via `--limit 0`.

## Hasil (macro-F1, sampel 150/task)

| Provider | Sentimen | Emosi | Toksisitas | Kecepatan |
|---|---|---|---|---|
| lexicon (`lexicon-v0`) | 0.537 | 0.210 | 0.418 | ~50.000/dtk |
| **indobert** (`indobert-multi`, CPU) | **0.907** | **0.726** | **0.854** | ~5–6/dtk |
| flash (`flash:openrouter`) | 0.864 | 0.576 | 0.735 | ~1–2/dtk |

Detail per-kelas (P/R/F1) tercetak oleh skrip. Gate PRD §7.4: macro-F1 sentimen ≥ 0.82.

## Kesimpulan

- **IndoBERT lokal = pilihan produksi.** Menang di ketiga task, memenuhi gate sentimen
  (0.907 ≥ 0.82), berjalan di CPU (~5–6 dok/dtk), **gratis per-panggilan**, dan **tak
  keluar infra** (selaras `data_policy=local_only`, UU PDP).
- **Flash (LLM API)** akurat tapi konsisten di bawah IndoBERT, **~30× lebih lambat**, dan
  data komentar keluar infra. Cocok sebagai **cadangan** atau untuk domain di luar
  cakupan model lokal — bukan default.
- **Lexicon** memadai sebagai baseline tanpa dependensi (mem-bootstrap pipeline), tapi
  lemah untuk emosi/toksisitas — jangan dipakai produksi.

Set `CLASSIFIER_PROVIDER=indobert` untuk produksi; `lexicon` default agar jalan tanpa GPU;
`flash` untuk bake-off/cadangan (butuh `LLM_PROVIDER` nyata).

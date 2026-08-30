# notebooks/

Notebook GPU cloud gratis untuk job berat (klasifikasi + embedding) tanpa migrasi GPU
lokal. Lihat juga `docs/gpu-migration.md` §10.

## Isi

- **`kaggle_colab_gpu.py`** — skrip format "percent" (`# %%` / `# %% [markdown]`), bisa
  dibuka sebagai notebook lewat `jupytext`, atau disalin cell-per-cell ke Kaggle
  Notebook / Google Colab. Menjalankan klasifikasi (sentimen/emosi/toksisitas) +
  embedding (multilingual-e5-small) memakai model yang sama dengan proyek Zandar
  OSINT, di GPU T4 gratis. Termasuk sel bonus opsional untuk kerangka fine-tuning.

## Cara pakai — Kaggle

1. Buka https://www.kaggle.com/code → **New Notebook**.
2. Panel kanan → **Settings** → **Accelerator** → pilih **GPU T4 x1**.
3. Panel kanan → **Settings** → **Internet** → nyalakan **On** (dibutuhkan untuk
   mengunduh model dari Hugging Face Hub saat notebook jalan).
4. Panel kanan → **Add Input** → **Upload** → upload CSV komentar kamu (kolom wajib:
   `content`). Kaggle akan menaruhnya di `/kaggle/input/<nama-dataset>/<file>.csv`.
5. Buka `kaggle_colab_gpu.py` di editor teks, salin isi tiap sel (dipisah `# %%`) ke
   sel baru di notebook Kaggle, urut dari atas ke bawah.
6. Di sel **§4 Upload data komentar**, ganti baris `INPUT_CSV = "/kaggle/input/..."`
   sesuai path dataset yang kamu upload di langkah 4.
7. Jalankan semua sel (*Run All*). Hasil (`hasil_klasifikasi_embedding.csv`) muncul di
   panel **Output** (kanan) — unduh dari sana.

Kuota gratis Kaggle: GPU ±30 jam/minggu, sesi maksimum ±9 jam berjalan.

## Cara pakai — Google Colab

1. Buka https://colab.research.google.com → **New Notebook**.
2. Menu **Runtime** → **Change runtime type** → **Hardware accelerator** → **T4 GPU**
   → **Save**.
3. Buka `kaggle_colab_gpu.py`, salin isi tiap sel (dipisah `# %%`) ke sel baru di
   Colab, urut dari atas ke bawah.
4. Di sel **§4 Upload data komentar**, jalankan sel tersebut — dialog upload file
   browser akan muncul otomatis (tak perlu edit path secara manual seperti Kaggle).
5. Jalankan sisa sel berurutan. Hasil (`hasil_klasifikasi_embedding.csv`) otomatis
   ter-download lewat browser di sel §7.

Kuota gratis Colab: sesi ±12 jam, GPU **tidak dijamin tersedia** di jam sibuk (kadang
dapat CPU-only meski sudah diset GPU — cek `torch.cuda.is_available()` di sel §1
sebelum lanjut, ulangi request runtime kalau `False`).

## Format CSV input

Wajib satu kolom bernama **`content`** berisi teks komentar (satu baris = satu
komentar). Kolom lain bebas — disalin apa adanya ke file hasil. Contoh minimal:

```csv
content
"Kebijakan ini bagus, akhirnya ada perhatian ke daerah pinggiran."
"Kok bisa harga naik terus, rakyat kecil makin susah."
```

## Setelah punya hasil

File `hasil_klasifikasi_embedding.csv` berisi kolom asli + `sentiment`,
`sentiment_score`, `emotion`, `toxicity`, dan (opsional) `embedding` (vektor 384-dim
sebagai string). Import balik ke pipeline Zandar OSINT sesuai kebutuhan investigasi —
notebook ini tidak menulis langsung ke Postgres/Qdrant proyek (sengaja terisolasi dari
infra lokal, supaya aman dijalankan dari environment cloud pihak ketiga).

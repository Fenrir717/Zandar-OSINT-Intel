# Migrasi GPU (Opsional) — Python 3.11 + CUDA untuk RTX 3050

Panduan ini untuk memindahkan jalur ML (`CLASSIFIER_PROVIDER=indobert`,
`EMBED_PROVIDER=local`) dari CPU (Python 3.14, torch CPU-only, `.venv` saat ini) ke
GPU (Python 3.11 + torch CUDA, `.venv311` **baru di sebelah** `.venv`) — atau alternatifnya,
menjalankan job berat sekali-jalan di GPU gratis Kaggle/Colab tanpa mengubah apa pun secara
lokal.

**Sifatnya opsional.** Sistem sudah dan tetap jalan penuh di CPU. Baca ini kalau kamu
punya banyak komentar yang perlu diklasifikasi/embedding, dan RTX 3050 di mesin ini
menganggur.

---

## 1. Kenapa GPU — dan kapan TIDAK perlu

Jalur berat di proyek ini ada dua: **klasifikasi IndoBERT** (`workers/classify/indobert.py`,
3 model RoBERTa berjalan berurutan per batch: sentimen, emosi, toksisitas) dan
**embedding lokal** (`workers/embed/local.py`, multilingual-e5-small, sekali per komentar
untuk Qdrant). Keduanya inference murni (bukan training) — kandidat bagus untuk percepatan
GPU karena kerjanya matriks-berat dan gampang dibatch.

Perkiraan percepatan realistis untuk beban ini: **~5–15× lebih cepat** dibanding CPU,
tergantung panjang teks, ukuran batch, dan seberapa panas GPU-nya. Angka ini **estimasi**
(lihat tabel §7) — bukan jaminan, dan RTX 3050 laptop/desktop bisa beda ~20-30%.

**Kapan GPU TIDAK perlu:**
- Skala kecil — beberapa ratus/ribu komentar per hari selesai dalam hitungan menit di CPU.
  Angka nyata terukur di `docs/classifier-bakeoff.md`: IndoBERT CPU ≈ 5–6 dok/dtik untuk
  klasifikasi 3-model sekaligus.
- Tidak ada job batch besar terjadwal — beban harian kecil tak butuh GPU.
- Kamu tidak mau mengelola driver NVIDIA/CUDA tambahan di mesin dev.
- Kamu cuma butuh GPU **sesekali** untuk backfill besar — pertimbangkan §8 (Kaggle/Colab
  gratis) alih-alih migrasi lokal permanen.

Kalau salah satu di atas cocok, cukup jalankan `scripts/bench_device.py` (§6) untuk
memastikan CPU sudah cukup — tak perlu lanjut ke migrasi.

---

## 2. Kenapa Python 3.11 (bukan 3.14 yang dipakai `.venv` sekarang)

`.venv` proyek ini dibuat dengan **Python 3.14** (CPU-only). Wheel torch dengan dukungan
CUDA **belum tersedia matang untuk Python 3.14** di PyPI/index resmi PyTorch — build CUDA
paling stabil & teruji ada untuk **Python 3.11** (juga `requires-python = ">=3.11"` di
`pyproject.toml`, jadi 3.11 tetap kompatibel dengan seluruh dependensi proyek).

Karena itu migrasi ini membuat **venv terpisah**, bukan mengganti Python di `.venv` yang ada.

---

## 3. Prasyarat

1. **Python 3.11** terpasang dan bisa dipanggil lewat Python launcher Windows:
   ```powershell
   py -3.11 --version
   ```
   Kalau belum ada, pasang salah satu:
   - `winget install Python.Python.3.11`
   - atau unduh installer dari https://www.python.org/downloads/release/python-3119/
     (centang **"Add python.exe to PATH"** saat instalasi)

   `scripts/migrate_py311.ps1` **tidak memasang Python secara otomatis** — kalau tidak
   ditemukan, skrip berhenti dan menampilkan instruksi ini.

2. **Driver NVIDIA terbaru** (Game Ready atau Studio) yang mendukung CUDA 12.1+. Cek versi
   & bahwa GPU terdeteksi:
   ```powershell
   nvidia-smi
   ```
   Kalau `nvidia-smi` tidak dikenali, pasang/update driver dari
   https://www.nvidia.com/Download/index.aspx sebelum lanjut.

3. RTX 3050 kamu (4GB VRAM, arsitektur Ampere/sm_86) — sudah didukung penuh oleh build
   CUDA 12.1 (`cu121`) yang dipakai skrip migrasi.

---

## 4. Langkah migrasi (NON-DESTRUKTIF)

Semua langkah ini membuat `.venv311` **baru**, di sebelah `.venv` yang sudah ada.
**`.venv` lama sama sekali tidak disentuh, tidak diubah, tidak dihapus** — layanan yang
sedang berjalan dari `.venv` (uvicorn/worker/beat) tidak terganggu.

Dari root proyek:

```powershell
powershell -File scripts\migrate_py311.ps1
```

Skrip ini (idempoten — aman dijalankan ulang):
1. Cek `py -3.11` tersedia (keluar dengan instruksi kalau tidak).
2. Buat `.venv311` dengan `py -3.11 -m venv .venv311` (dilewati kalau sudah ada).
3. `pip install -U pip`, lalu `pip install -e ".[ml]"` (install proyek + torch CPU default
   + transformers).
4. **Ganti** torch dengan build CUDA: `pip uninstall -y torch` lalu
   `pip install torch --index-url https://download.pytorch.org/whl/cu121` (cu121 cocok
   Ampere/RTX 3050).
5. Verifikasi: cetak `torch.__version__`, `torch.cuda.is_available()`, dan nama GPU.

Proses ini bisa makan waktu 5-15 menit tergantung koneksi (wheel CUDA torch besar,
~2.5GB).

---

## 5. Verifikasi GPU

Langkah 5 skrip migrasi sudah mencetak ini otomatis, tapi bisa dicek ulang kapan saja:

```powershell
.\.venv311\Scripts\python.exe -c "import torch; print(torch.__version__); print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else '-')"
```

Output yang diharapkan kira-kira:
```
2.x.x+cu121
CUDA: True
GPU: NVIDIA GeForce RTX 3050 ...
```

Kalau `CUDA: False` — cek driver (`nvidia-smi`), pastikan tidak ada VPN/proxy yang
memotong download wheel CUDA (ukurannya besar, kadang gagal diam-diam jadi fallback ke
build CPU), dan coba jalankan ulang langkah 4 skrip migrasi secara manual:
```powershell
.\.venv311\Scripts\python.exe -m pip uninstall -y torch
.\.venv311\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu121
```

Lalu jalankan benchmark nyata (§6) untuk melihat throughput sungguhan model kita di GPU.

---

## 6. Mengarahkan servis ke `.venv311` (tanpa menghapus `.venv`)

Servis (`api.main:app` via uvicorn, Celery worker, Celery beat) menentukan Python-nya lewat
path venv yang dipanggil — bukan lewat variabel lingkungan. Jadi "pindah ke GPU" berarti
memanggil `.venv311\Scripts\python.exe` alih-alih `.venv\Scripts\python.exe`, **sementara**
`.env` diset `CLASSIFIER_PROVIDER=indobert` dan `EMBED_PROVIDER=local` (default proyek
`lexicon`/`stub` tidak memuat torch sama sekali, jadi GPU baru kepakai kalau dua env var
ini diaktifkan — cek `.env.example`).

**Cara 1 — jalankan langsung dari `.venv311` (paling aman, tak ubah file apa pun):**
```powershell
# API
.\.venv311\Scripts\python.exe -m uvicorn api.main:app --reload

# Celery worker (sama seperti scripts/run_worker.ps1, tapi python dari .venv311)
.\.venv311\Scripts\python.exe -m celery -A workers.celery_app worker `
    --loglevel=info --pool=threads -Q default,collect `
    --without-mingle --without-gossip --without-heartbeat

# Celery beat
.\.venv311\Scripts\python.exe -m celery -A workers.celery_app beat --loglevel=info
```

**Cara 2 — ubah sementara `scripts\run_worker.ps1` / `scripts\run_beat.ps1`:** ganti baris
`.\.venv\Scripts\python.exe` menjadi `.\.venv311\Scripts\python.exe`, lalu kembalikan lagi
kalau mau rollback. Kit ini **tidak** mengubah kedua file itu secara otomatis — ini pilihan
manual kamu, supaya tidak ada risiko servis existing tiba-tiba ikut berubah.

Jalankan `.venv` (CPU) dan `.venv311` (GPU) **tidak boleh bersamaan untuk servis yang sama**
(port bentrok, worker Celery rebutan queue) — pilih salah satu per sesi kerja, atau
jalankan worker GPU di queue terpisah kalau memang perlu keduanya hidup bersamaan.

---

## 7. Catatan VRAM 4GB (RTX 3050)

Model yang kita pakai — 3× IndoBERT/RoBERTa-base (~110–125M parameter tiap model) untuk
sentimen/emosi/toksisitas, plus multilingual-e5-small (~118M) untuk embedding — **cukup
kecil untuk semuanya sekaligus muat di 4GB**, asal:

- **fp16** dipakai untuk inference (`workers/classify/indobert.py` sudah otomatis pilih
  `torch.float16` saat `torch.cuda.is_available()` — tidak perlu diubah manual).
- **Batch sedang** (kode sudah pakai `batch_size=32` untuk klasifikasi dan embedding) —
  jangan naikkan drastis (mis. >128) di GPU 4GB, terutama untuk teks panjang; kalau muncul
  `CUDA out of memory`, turunkan batch di kode provider bersangkutan.
- Jangan jalankan training/fine-tuning penuh di GPU 4GB lokal ini secara bersamaan dengan
  inference produksi — VRAM akan penuh. Untuk fine-tuning, pakai Kaggle/Colab (§8), yang
  punya GPU dengan VRAM jauh lebih besar (T4 16GB) secara gratis.

3 model klasifikasi + 1 model embedding dimuat bersamaan (worker Celery memuat semuanya di
`IndoBertClassifier.__init__` dan `LocalEmbedder.__init__`) memakai sekitar **1.5–2.5GB**
VRAM dalam fp16 — masih ada ruang aman di 4GB untuk activation/batch overhead.

---

## 8. Benchmark: bandingkan sebelum vs sesudah

Skrip `scripts/bench_device.py` mengukur throughput nyata (dok/detik) untuk klasifikasi
IndoBERT dan embedding lokal, di device manapun ia dijalankan (CPU atau GPU — terdeteksi
otomatis). Ambil ~200 komentar dari DB kalau tersedia, atau teks sintetis kalau DB
kosong/mati.

```powershell
# Baseline CPU (venv lama)
.\.venv\Scripts\python.exe scripts\bench_device.py

# Setelah migrasi, GPU (venv baru)
.\.venv311\Scripts\python.exe scripts\bench_device.py
```

Bandingkan baris `Throughput` dari kedua run untuk melihat percepatan sungguhan di mesin
kamu — jauh lebih dipercaya daripada angka estimasi di tabel bawah.

---

## 9. Tabel throughput — ESTIMASI untuk 100.000 komentar

| Tahap | CPU (angka nyata, `docs/classifier-bakeoff.md`) | RTX 3050 4GB (**estimasi**) | Percepatan (**estimasi**) |
|---|---|---|---|
| Klasifikasi (3 model: sentimen+emosi+toksisitas) | ~5–6 dok/dtk (≈ 4.6–5.6 jam / 100rb) | ~50–100 dok/dtk (≈ 17–33 menit / 100rb) | ~10–17× |
| Embedding (e5-small) | ~20 dok/dtk (≈ 1.4 jam / 100rb) | ~200–400 dok/dtk (≈ 4–8 menit / 100rb) | ~10–20× |

Kolom CPU klasifikasi diambil dari pengukuran nyata di `docs/classifier-bakeoff.md`
(indobert-multi, CPU). Kolom CPU embedding dan **seluruh kolom RTX 3050 adalah estimasi**
berbasis karakteristik model (RoBERTa-base/e5-small, fp16, batch 32) — jalankan
`scripts/bench_device.py` di kedua device untuk angka nyata di mesinmu sendiri. Waktu
total makin cepat kalau batch dinaikkan (dalam batas VRAM §7) atau teks pendek (komentar
medsos umumnya pendek).

---

## 10. Alternatif: GPU gratis di cloud (tanpa migrasi lokal)

Untuk backfill besar sekali-jalan (mis. re-klasifikasi seluruh histori komentar), migrasi
lokal permanen mungkin berlebihan. `notebooks/kaggle_colab_gpu.py` menyediakan skrip
self-contained untuk dijalankan di **Kaggle atau Google Colab** (GPU T4 gratis, VRAM jauh
lebih besar dari RTX 3050): upload CSV komentar, jalankan klasifikasi+embedding di GPU
cloud, unduh hasilnya, tanpa menyentuh mesin lokal sama sekali. Lihat
`notebooks/README.md` untuk cara pakai.

---

## 11. Rollback

Migrasi ini tidak mengubah apa pun di `.venv` atau file proyek lain. Untuk kembali ke CPU
sepenuhnya:

1. Berhenti memanggil `.venv311\Scripts\python.exe` untuk servis (kembali panggil
   `.venv\Scripts\python.exe`, atau jalankan `scripts\run_worker.ps1` /
   `scripts\run_beat.ps1` seperti biasa — keduanya sudah menunjuk `.venv`).
2. (Opsional) Hapus `.venv311` kalau tidak dibutuhkan lagi:
   ```powershell
   Remove-Item -Recurse -Force .venv311
   ```
   Ini aman — `.venv` lama tidak pernah tersentuh oleh proses migrasi maupun rollback.

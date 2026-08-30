# Export PDF Laporan (Riset Pasar Geospasial)

Tombol **Unduh PDF** di halaman Riset Pasar merender laporan HTML → PDF **di sisi
server** dengan **Chromium headless** (`geo/pdf.py`). Dipilih server-side (bukan
dialog cetak browser) supaya hasilnya **konsisten lintas browser/OS**, background
tercetak, dan **link tetap bisa diklik** (mis. tautan "peta ↗" ke Google Maps).

## Kebutuhan runtime

Proses **API** (uvicorn) harus bisa menemukan biner Chromium di host tempat ia
berjalan. Urutan pencarian di `geo/pdf.py`:

1. Env `CHROME_BIN` (path eksplisit) — dicoba pertama.
2. Path umum Windows: Google Chrome, lalu Microsoft Edge.
3. `PATH`: `chrome`, `msedge`, `chromium`, `chromium-browser`.

Kalau tak ada, endpoint `/market/report.pdf` mengembalikan **502** dengan pesan
jelas, dan tombol UI menyarankan pakai **Unduh HTML** (lalu cetak dari browser)
sebagai jalan sementara. Fitur lain tidak terpengaruh.

### Windows (dev sekarang)
Tak perlu apa-apa — **Microsoft Edge selalu ada**. Terdeteksi otomatis.

### Linux / Docker (saat API dikontainerkan nanti)

> Catatan: `docker-compose.yml` saat ini **infra saja** (Postgres, Redis, Qdrant,
> Neo4j, MinIO, Langfuse). API & worker masih jalan di host, jadi belum ada image
> API untuk dipasangi Chromium. Saat kamu membuat image API, pilih salah satu:

**Opsi A — pasang Chromium DI DALAM image API (paling sederhana).**
Tambahkan ke Dockerfile API:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
      chromium fonts-liberation fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
ENV CHROME_BIN=/usr/bin/chromium
```
`geo/pdf.py` sudah memakai `--no-sandbox` (wajib untuk root di container).

**Opsi B — service browser terpisah (browserless) di compose.**
Untuk skala/isolasi, jalankan browser sebagai service dan bicara via CDP alih-alih
subprocess. Ini butuh perubahan `geo/pdf.py` (dari `subprocess` ke koneksi WebSocket
CDP / library seperti Playwright). Contoh service:
```yaml
  chrome:
    image: ghcr.io/browserless/chromium:latest
    ports: ["3000:3000"]
    restart: unless-stopped
```
Lalu render lewat endpoint CDP browserless. **Belum diimplementasikan** — pilih ini
hanya bila Opsi A tak cukup.

## Uji cepat
```bash
# host punya Chrome/Edge?
python -c "from geo.pdf import find_chromium; print(find_chromium())"
```
Kalau mencetak path biner → siap. `None` → set `CHROME_BIN` atau pasang Chromium.

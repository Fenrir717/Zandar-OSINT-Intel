"""Benchmark IndoBERT classifier + embedder lokal (e5-small) pada device SAAT INI.

Device (CPU atau CUDA) terdeteksi otomatis dari torch — skrip ini tidak
membutuhkan argumen device. Untuk membandingkan CPU vs GPU: jalankan sekali dari
`.venv` (CPU) dan sekali dari `.venv311` (GPU, setelah migrasi — lihat
docs/gpu-migration.md), lalu bandingkan baris "Throughput" dari kedua run.

Ambil ~200 komentar NYATA dari DB (SessionLocal + Comment). Kalau DB tidak bisa
diakses (infra mati) atau tabel `comments` kosong, jatuh ke teks sintetis
Bahasa Indonesia ala-komentar-medsos supaya skrip tetap bisa jalan tanpa infra.

    .venv\\Scripts\\python.exe scripts\\bench_device.py
    .venv311\\Scripts\\python.exe scripts\\bench_device.py --n 300
"""

from __future__ import annotations

import argparse
import asyncio
import time

# Teks sintetis Bahasa Indonesia (gaya komentar medsos/OSINT) dipakai sebagai
# fallback bila DB kosong/tak terjangkau. Dicampur beragam sentimen/topik agar
# tidak bias ke satu label saat benchmark.
_SYNTHETIC_TEXTS: list[str] = [
    "Kebijakan baru ini bagus banget, akhirnya ada perhatian ke daerah pinggiran.",
    "Kok bisa ya harga BBM naik lagi, rakyat kecil makin susah aja hidupnya.",
    "Menurut saya ini masih perlu dikaji ulang, datanya belum lengkap.",
    "Mantap min, terima kasih sudah update infonya secepat ini!",
    "Saya kecewa berat sama pelayanan di kantor kelurahan, lambat banget prosesnya.",
    "Ada yang tau jadwal pastinya kapan program ini mulai berjalan?",
    "Setuju sih kalau infrastruktur jalan diperbaiki dulu sebelum proyek lain.",
    "Ini hoaks kan ya? tolong jangan asal share info yang belum jelas sumbernya.",
    "Alhamdulillah akhirnya listrik desa kami nyala 24 jam, terima kasih pemerintah.",
    "Kenapa anggarannya segitu besar tapi hasil di lapangan gak keliatan sama sekali.",
    "Netral aja sih menurut saya, tunggu hasil evaluasi enam bulan ke depan.",
    "Warga di sini udah lama nunggu jembatan ini selesai, semoga tepat waktu.",
    "Tolong pak, jalan di kampung kami rusak parah sejak banjir kemarin.",
    "Info ini sangat membantu buat riset saya, makasih banyak sudah dibagikan.",
    "Miris lihat berita ini, semoga ada tindakan tegas dari pihak berwenang.",
    "Program bansos tahun ini datanya lebih rapi dibanding tahun lalu, bagus.",
    "Saya rasa perlu transparansi lebih soal penggunaan dana desa ini.",
    "Selamat untuk tim yang sudah bekerja keras menyelesaikan proyek ini tepat waktu.",
    "Kenapa selalu telat pengumumannya, jadi banyak yang ketinggalan info penting.",
    "Semoga kedepannya pelayanan publik makin cepat dan tidak berbelit-belit lagi.",
]


async def _fetch_from_db(limit: int) -> list[str]:
    """Ambil `limit` konten komentar dari Postgres. Biarkan exception naik ke
    caller — _load_texts yang menangani fallback (DB mati/tak terkonfigurasi)."""
    from sqlalchemy import select

    from core.db import SessionLocal, engine
    from core.models import Comment

    async with SessionLocal() as session:
        rows = (await session.execute(select(Comment.content).limit(limit))).all()
    await engine.dispose()
    return [row[0] for row in rows if row[0]]


def _synthetic_texts(n: int) -> list[str]:
    return [_SYNTHETIC_TEXTS[i % len(_SYNTHETIC_TEXTS)] for i in range(n)]


def _load_texts(n: int) -> tuple[list[str], str]:
    """Kembalikan (teks, label_sumber). Tak pernah melempar — selalu ada fallback."""
    try:
        texts = asyncio.run(_fetch_from_db(n))
    except Exception as exc:  # DB mati, kredensial salah, driver hilang, dll.
        print(f"  [!] Tak bisa mengambil dari DB ({exc!r}) -> pakai teks sintetis.")
        return _synthetic_texts(n), "sintetis (DB tak terjangkau)"

    if not texts:
        print("  [!] Tabel 'comments' kosong -> pakai teks sintetis.")
        return _synthetic_texts(n), "sintetis (DB kosong)"

    if len(texts) < n:
        print(f"  [!] DB hanya punya {len(texts)} baris -> digenapkan dengan teks sintetis.")
        texts = texts + _synthetic_texts(n - len(texts))

    return texts[:n], "DB nyata (tabel comments)"


def _device_info() -> tuple[str, str | None]:
    """Kembalikan (nama_device, nama_gpu_atau_none). Impor torch LAZY & aman."""
    try:
        import torch
    except ImportError:
        return "cpu (torch tidak terpasang)", None
    if torch.cuda.is_available():
        return "cuda", torch.cuda.get_device_name(0)
    return "cpu", None


def _bench_classifier(texts: list[str]) -> None:
    print("\n[2/3] IndoBertClassifier.classify (sentimen + emosi + toksisitas)...")
    try:
        from workers.classify.indobert import IndoBertClassifier
    except Exception as exc:
        print(f"  [!] Tak bisa impor IndoBertClassifier: {exc!r}")
        print('      Pasang extra ml:  pip install -e ".[ml]"')
        return

    try:
        clf = IndoBertClassifier()
    except Exception as exc:
        print(f"  [!] Gagal memuat model classifier: {exc!r}")
        return

    t0 = time.time()
    labels = clf.classify(texts)
    dt = time.time() - t0
    rate = len(texts) / dt if dt > 0 else 0.0

    print(f"  Model       : {clf.version}")
    print(f"  Dokumen     : {len(texts)}")
    print(f"  Waktu       : {dt:.2f}s")
    print(f"  Throughput  : {rate:.2f} dok/dtk")
    if labels:
        first = labels[0]
        print(f"  Contoh out  : sentiment={first.sentiment} emotion={first.emotion} toxicity={first.toxicity}")


def _bench_embedder(texts: list[str]) -> None:
    print("\n[3/3] LocalEmbedder.embed (multilingual-e5-small)...")
    try:
        from workers.embed.local import LocalEmbedder
    except Exception as exc:
        print(f"  [!] Tak bisa impor LocalEmbedder: {exc!r}")
        print('      Pasang extra ml:  pip install -e ".[ml]"')
        return

    try:
        emb = LocalEmbedder()
    except Exception as exc:
        print(f"  [!] Gagal memuat model embedder: {exc!r}")
        return

    t0 = time.time()
    vectors = emb.embed(texts, kind="passage")
    dt = time.time() - t0
    rate = len(texts) / dt if dt > 0 else 0.0

    print(f"  Model       : {emb.version}")
    print(f"  Dimensi     : {emb.dim}")
    print(f"  Dokumen     : {len(texts)}")
    print(f"  Waktu       : {dt:.2f}s")
    print(f"  Throughput  : {rate:.2f} dok/dtk")
    if vectors:
        print(f"  Contoh out  : vektor panjang {len(vectors[0])}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=200, help="jumlah komentar dibenchmark (default 200)")
    args = ap.parse_args()

    device, gpu_name = _device_info()

    print("=" * 70)
    print(" Zandar OSINT — benchmark device (klasifikasi + embedding)")
    print("=" * 70)
    print(f"  Device      : {device}" + (f" ({gpu_name})" if gpu_name else ""))

    print(f"\n[1/3] Menyiapkan {args.n} teks...")
    texts, sumber = _load_texts(args.n)
    print(f"  Sumber teks : {sumber}")
    print(f"  Jumlah teks : {len(texts)}")

    _bench_classifier(texts)
    _bench_embedder(texts)

    print("\n" + "=" * 70)
    print(" Selesai. Bandingkan angka 'Throughput' dengan hasil di venv lain")
    print(" (mis. jalankan skrip ini di .venv CPU lalu di .venv311 GPU).")
    print(" Lihat docs/gpu-migration.md §9 untuk konteks tabel estimasi.")
    print("=" * 70)


if __name__ == "__main__":
    main()

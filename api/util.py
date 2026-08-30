"""Utilitas kecil lintas-router."""
from fastapi import HTTPException, status


def enqueue(task, *args):
    """Kirim task Celery dengan aman.

    ``.delay()`` bisa gagal bila broker (Redis) mati atau argumen tak bisa
    diserialisasi. Tanpa penjagaan, kegagalan itu muncul sebagai 500 buram.
    Bungkus jadi 503 yang jujur agar frontend bisa memberi tahu user "antrean
    tidak tersedia", bukan "error tak dikenal".

    Catatan: untuk endpoint yang sudah meng-commit baris berstatus (mis.
    CollectionRun "queued") SEBELUM enqueue, jangan pakai helper ini apa
    adanya — tandai baris itu "failed" dulu agar tidak menggantung, lalu 503.
    """
    try:
        return task.delay(*args)
    except Exception as exc:  # noqa: BLE001 — broker/serialisasi apa pun → 503
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Antrean task tidak tersedia (broker Redis mati?). Coba lagi nanti.",
        ) from exc

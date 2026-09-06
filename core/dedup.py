"""Eliminasi data cacat — collapse spam/bot yang mengulang konten identik.

Riset (2026-09): pada scan tertentu sampai ~43% komentar = SATU akun bot memposting
pesan sama ratusan kali (mis. bank BCA: "Group Telegram Resmi Bank BCA..." 791× dari
1 akun; scam "OJK...INVESTMENT TRADING" 50×). Repetisi ini MENGGELEMBUNGKAN semua
analisis berbasis-frekuensi (sentimen, entitas, SoV, keyword) — hasil jadi bias.

Fungsi ini menandai duplikat-spam agar dihitung SEKALI (kemunculan pertama disimpan,
sisanya dibuang dari analisis). BUKAN menghapus data mentah — hanya menormalkan bobot.

Spam-duplikat = dedup_hash sama, muncul >=MIN_COPIES kali dari <=MAX_AUTHORS akun
(pola bot). Ini SENGAJA konservatif: "banyak orang kebetulan menulis sama" (organik/
viral) TIDAK dibuang karena akun-nya banyak. Buzzer TIDAK memakai ini — ia justru
butuh repetisi mentah untuk mendeteksi spam.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

MIN_COPIES = 5   # <5 salinan → biarkan (bukan spam masif)
MAX_AUTHORS = 2  # >2 akun berbeda → anggap organik (bukan 1 bot)


def spam_keep_mask(
    author_hashes: Sequence[str | None], dedup_hashes: Sequence[str | None]
) -> list[bool]:
    """→ list[bool] sejajar input: True=simpan, False=buang (duplikat-spam).

    Menyimpan kemunculan PERTAMA tiap klaster spam, membuang salinan sisanya.
    Baris tanpa dedup_hash selalu disimpan (tak bisa dinilai duplikatnya)."""
    n = len(dedup_hashes)
    groups: dict[str, dict] = defaultdict(lambda: {"authors": set(), "idx": []})
    for i in range(n):
        d = dedup_hashes[i]
        if not d:
            continue
        g = groups[d]
        g["authors"].add(author_hashes[i])
        g["idx"].append(i)

    drop: set[int] = set()
    for g in groups.values():
        if len(g["idx"]) >= MIN_COPIES and len(g["authors"]) <= MAX_AUTHORS:
            drop.update(g["idx"][1:])  # buang semua kecuali yang pertama
    return [i not in drop for i in range(n)]


def keep_rows(rows: list, author_idx: int = 0, dedup_idx: int = 1) -> list:
    """Saring list-of-tuple: buang baris duplikat-spam (kolom author & dedup by index)."""
    if not rows:
        return rows
    mask = spam_keep_mask([r[author_idx] for r in rows], [r[dedup_idx] for r in rows])
    return [r for r, keep in zip(rows, mask, strict=False) if keep]

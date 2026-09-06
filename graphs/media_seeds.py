"""Katalog media Indonesia terverifikasi — tulang punggung deterministik untuk sitemap.

Melengkapi agen Recon (DuckDuckGo + benih LLM yang non-deterministik) dengan media
besar Indonesia yang PASTI relevan & terverifikasi mengekspos sitemap yang bisa
ditelusuri. Tiga kategori supaya riset bisnis/brand tak cuma dapat berita umum:

- umum      : Kompas, Detik, Liputan6, Merdeka, CNN Indonesia, Kumparan
- bisnis    : CNBC Indonesia, Katadata, Warta Ekonomi
- investasi : Kontan, Bareksa, IDX Channel

Semua root SUDAH diuji live (discover + walk sitemap menghasilkan URL nyata). Root
yang gagal/diblok TIDAK dimasukkan — jujur, tanpa benih mati.
"""

from __future__ import annotations

CATEGORIES = ("umum", "bisnis", "investasi")

# (nama, root, kategori)
ID_MEDIA: list[tuple[str, str, str]] = [
    ("Kompas", "https://www.kompas.com", "umum"),
    ("Detik", "https://www.detik.com", "umum"),
    ("Liputan6", "https://www.liputan6.com", "umum"),
    ("Merdeka", "https://www.merdeka.com", "umum"),
    ("CNN Indonesia", "https://www.cnnindonesia.com", "umum"),
    ("Kumparan", "https://kumparan.com", "umum"),
    ("CNBC Indonesia", "https://www.cnbcindonesia.com", "bisnis"),
    ("Katadata", "https://katadata.co.id", "bisnis"),
    ("Warta Ekonomi", "https://wartaekonomi.co.id", "bisnis"),
    ("Kontan", "https://www.kontan.co.id", "investasi"),
    ("Bareksa", "https://www.bareksa.com", "investasi"),
    ("IDX Channel", "https://www.idxchannel.com", "investasi"),
]


def media_by_category(categories: list[str] | None = None) -> list[tuple[str, str, str]]:
    cats = set(categories) if categories else set(CATEGORIES)
    return [m for m in ID_MEDIA if m[2] in cats]


def _spread(media: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """Susun round-robin lintas kategori → subset kecil tetap campur (umum+bisnis+investasi)."""
    buckets = {c: [m for m in media if m[2] == c] for c in CATEGORIES}
    out: list[tuple[str, str, str]] = []
    while any(buckets.values()):
        for c in CATEGORIES:
            if buckets[c]:
                out.append(buckets[c].pop(0))
    return out


def sitemap_sources(
    keywords: list[str],
    categories: list[str] | None = None,
    per_site: int = 80,
    limit: int | None = None,
) -> list[dict]:
    """→ spec sumber `sitemap` (satu per portal). match='url' (murah): hanya artikel
    yang slug-nya cocok keyword yang diekstrak, jadi portal tak-relevan ~gratis.

    Default (categories=None) di-spread lintas kategori supaya media bisnis/investasi
    selalu ikut bila di-limit — bukan cuma umum."""
    media = media_by_category(categories)
    if categories is None:
        media = _spread(media)
    if limit:
        media = media[:limit]
    return [
        {
            "platform": "sitemap",
            "query": {
                "url": root, "keywords": keywords, "match": "url",
                "max_articles": per_site, "max_urls": 3000,
            },
            "est_items": per_site,
        }
        for _name, root, _cat in media
    ]

"""Share of Voice (SoV) + NSS — perbandingan merek vs kompetitor.

Standar korporat brand-health: bukan cuma "sentimen brand-ku", tapi POSISI RELATIF
terhadap kompetitor di percakapan publik.

- Share of Voice (SoV) = pangsa volume percakapan tiap merek dari total volume
  merek yang terdeteksi. Merek yang paling banyak dibicarakan memimpin percakapan.
- NSS (Net Sentiment Score) = %positif − %negatif per merek (rentang −100..+100).
  Volume tinggi belum tentu bagus — bisa ramai karena krisis. NSS memisahkan
  "ramai dipuji" dari "ramai dihujat".

Sumber merek: entitas tipe ORGANISASI hasil NER yang sudah teragregasi di knowledge
graph (name, mentions, pos/neg/neu per-target). Jadi SoV = tampilan hitung ulang di
atas data entitas-sentimen yang SUDAH ada — bukan pipeline baru, konsisten dgn
filosofi platform (deteksi lokal skala jutaan, tanpa LLM per komentar).
"""

from __future__ import annotations

# Tipe entitas yang dianggap "merek/kompetitor" untuk SoV (default: organisasi).
BRAND_TYPES: tuple[str, ...] = ("organization",)


def net_sentiment_score(pos: int, neg: int, neu: int) -> float | None:
    """NSS = (%positif − %negatif), rentang −100..+100. None bila tak ada data."""
    total = pos + neg + neu
    if total == 0:
        return None
    return round((pos - neg) / total * 100, 1)


def compute_sov(
    entities: list[dict], types: tuple[str, ...] = BRAND_TYPES, top: int = 10
) -> dict:
    """entities: [{name, type, mentions, pos, neg, neu, ...}] (dari graph.read_entities).

    → {brands:[{name, volume, share_of_voice, nss, pos, neg, neu}], total_volume,
       count, leader, caveats}. Diurutkan volume menurun; share_of_voice dalam %.
    """
    brands = [
        e for e in entities
        if e.get("type") in types and (e.get("mentions") or 0) > 0
    ]
    total_volume = sum(int(e["mentions"]) for e in brands)

    out = []
    for e in brands:
        vol = int(e["mentions"])
        pos, neg, neu = int(e.get("pos") or 0), int(e.get("neg") or 0), int(e.get("neu") or 0)
        out.append({
            "name": e.get("name"),
            "volume": vol,
            "share_of_voice": round(vol / total_volume * 100, 1) if total_volume else 0.0,
            "nss": net_sentiment_score(pos, neg, neu),
            "pos": pos, "neg": neg, "neu": neu,
        })
    out.sort(key=lambda d: d["volume"], reverse=True)

    return {
        "brands": out[:top],
        "total_volume": total_volume,
        "count": len(out),
        "leader": out[0]["name"] if out else None,
        "caveats": [
            "Merek = entitas tipe ORGANISASI hasil NER; produk/merek yang tak "
            "terdeteksi sebagai organisasi bisa terlewat.",
            "SoV relatif terhadap organisasi yang terdeteksi di investigasi ini "
            "(bukan seluruh pasar).",
        ],
    }

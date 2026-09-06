"""Skor reputasi agregat — memadukan RATING BINTANG (review app store, sinyal
langsung) dengan SENTIMEN TEKS (classifier) menjadi indeks reputasi 0-100 per
investigasi/brand.

Fungsi murni (tanpa IO) agar mudah diuji. Endgame: dashboard reputasi menampilkan
indeks + distribusi bintang + rincian per-platform + tren. Bintang diutamakan bila
ada (lebih tegas dari sentimen teks); tanpa bintang → jatuh ke sentimen murni.
"""

from __future__ import annotations

from statistics import mean

_STAR_WEIGHT = 0.65  # bobot komponen bintang saat rating tersedia (sisanya sentimen)


def _index_from_rating(avg_rating: float) -> float:
    """avg bintang 1-5 → 0-100 (1★=0, 5★=100)."""
    return max(0.0, min(100.0, (avg_rating - 1.0) / 4.0 * 100.0))


def _index_from_sentiment(avg_sent_score: float) -> float:
    """avg sentiment_score -1..1 → 0-100."""
    return max(0.0, min(100.0, (avg_sent_score + 1.0) / 2.0 * 100.0))


def aggregate_reputation(items: list[dict]) -> dict:
    """items: list of {rating:int|None (1-5), sentiment:str|None, sentiment_score:
    float|None, platform:str}. Kembalikan ringkasan reputasi agregat."""
    total = len(items)
    ratings = [int(it["rating"]) for it in items if it.get("rating") in (1, 2, 3, 4, 5)]
    sent_scores = [float(it["sentiment_score"]) for it in items
                   if it.get("sentiment_score") is not None]

    dist = {s: 0 for s in (1, 2, 3, 4, 5)}
    for r in ratings:
        dist[r] += 1
    avg_rating = round(mean(ratings), 2) if ratings else None
    avg_sent = round(mean(sent_scores), 3) if sent_scores else None

    sentiment_counts: dict[str, int] = {}
    for it in items:
        s = it.get("sentiment")
        if s:
            sentiment_counts[s] = sentiment_counts.get(s, 0) + 1

    # Indeks reputasi 0-100: bintang diutamakan bila cukup; jika tidak → sentimen.
    index = None
    basis = "tidak cukup data"
    if avg_rating is not None and avg_sent is not None:
        index = _STAR_WEIGHT * _index_from_rating(avg_rating) + (1 - _STAR_WEIGHT) * _index_from_sentiment(avg_sent)
        basis = f"bintang×{_STAR_WEIGHT:.0%} + sentimen×{1 - _STAR_WEIGHT:.0%}"
    elif avg_rating is not None:
        index = _index_from_rating(avg_rating)
        basis = "bintang saja"
    elif avg_sent is not None:
        index = _index_from_sentiment(avg_sent)
        basis = "sentimen saja (tak ada rating)"

    # Rincian per platform (rata bintang + jumlah)
    by_platform: dict[str, dict] = {}
    for it in items:
        p = it.get("platform") or "?"
        d = by_platform.setdefault(p, {"count": 0, "_ratings": []})
        d["count"] += 1
        if it.get("rating") in (1, 2, 3, 4, 5):
            d["_ratings"].append(int(it["rating"]))
    for d in by_platform.values():
        rs = d.pop("_ratings")
        d["avg_rating"] = round(mean(rs), 2) if rs else None
        d["rated"] = len(rs)

    return {
        "total": total,
        "rated_count": len(ratings),
        "avg_rating": avg_rating,
        "star_distribution": dist,
        "avg_sentiment_score": avg_sent,
        "sentiment_counts": sentiment_counts,
        "reputation_index": round(index, 1) if index is not None else None,
        "index_basis": basis,
        "by_platform": by_platform,
        "caveats": [
            "Indeks 0-100: gabungan rating bintang (diutamakan) + sentimen teks classifier.",
            "Rating hanya dari sumber review (playstore/appstore); sumber lain menyumbang sentimen teks.",
            "Bukan skor mutlak — untuk membandingkan brand/waktu secara relatif.",
        ],
    }

"""ABSA — Aspect-Based Sentiment Analysis (sentimen per-aspek bisnis).

Standar korporat: bukan cuma "Positif 60% / Negatif 40%", tapi pecah per ASPEK —
Harga, Produk/Kualitas, Pelayanan/CS, Pengiriman, Aplikasi/Sistem. Deteksi aspek =
leksikon kata kunci (lokal, murah, skala jutaan) — konsisten dgn filosofi platform
(model lokal untuk bulk, LLM hanya agregat).

Pendekatan v1: deteksi aspek per komentar (keyword) → atribusikan SENTIMEN dokumen
(hasil classifier) ke tiap aspek terdeteksi, lalu agregasi. Keterbatasan jujur:
komentar campur ("harga mahal tapi CS ramah") memakai satu sentimen dokumen untuk
kedua aspek — di tingkat AGREGAT (ribuan komentar) sinyal aspek dominan tetap
muncul (keluhan harga cenderung negatif, pujian CS cenderung positif).
"""

from __future__ import annotations

import re

# Aspek → (label tampilan, kata kunci). Kata kunci dicocokkan sebagai kata utuh.
ASPECTS: dict[str, tuple[str, list[str]]] = {
    "harga": ("Harga", [
        "harga", "mahal", "murah", "diskon", "promo", "kemahalan", "terjangkau",
        "worth", "ongkos", "kepacet", "hemat", "budget", "overprice",
    ]),
    "produk": ("Produk/Kualitas", [
        "kualitas", "produk", "barang", "rusak", "cacat", "awet", "palsu", "ori",
        "original", "abal", "premium", "bahan", "kw",
    ]),
    "pelayanan": ("Pelayanan/CS", [
        "admin", "cs", "layanan", "pelayanan", "respon", "ramah", "balas", "tanggap",
        "sopan", "judes", "seller", "penjual", "komunikatif", "cuek",
    ]),
    "pengiriman": ("Pengiriman", [
        "kirim", "pengiriman", "kurir", "paket", "sampai", "ongkir", "packing",
        "resi", "dikirim", "ekspedisi", "telat", "estimasi",
    ]),
    "aplikasi": ("Aplikasi/Sistem", [
        "aplikasi", "apk", "lag", "error", "bug", "update", "login", "loading",
        "crash", "lemot", "fitur", "sistem", "ngelag", "hang", "force",
    ]),
}

_PATTERNS: dict[str, re.Pattern] = {
    key: re.compile(r"\b(?:" + "|".join(re.escape(k) for k in kws) + r")\b", re.IGNORECASE)
    for key, (_lbl, kws) in ASPECTS.items()
}


def detect_aspects(text: str) -> list[str]:
    """Aspek yang disebut dalam teks (bisa lebih dari satu)."""
    t = text or ""
    return [key for key, pat in _PATTERNS.items() if pat.search(t)]


def aggregate_aspects(items: list[dict]) -> dict:
    """items: {text, sentiment} → rincian sentimen per aspek (pos/neg/neu, net, count)."""
    agg: dict[str, dict] = {
        k: {"aspect": k, "label": lbl, "pos": 0, "neg": 0, "neu": 0, "count": 0}
        for k, (lbl, _kw) in ASPECTS.items()
    }
    with_aspect = 0
    for it in items:
        aspects = detect_aspects(it.get("text", ""))
        if aspects:
            with_aspect += 1
        s = it.get("sentiment")
        bucket = "pos" if s in ("pos", "positive") else "neg" if s in ("neg", "negative") else "neu"
        for a in aspects:
            d = agg[a]
            d["count"] += 1
            d[bucket] += 1

    out = []
    for d in agg.values():
        c = d["count"]
        if c == 0:
            continue
        net = round((d["pos"] - d["neg"]) / c, 3)
        d["net_sentiment"] = net
        d["sentiment"] = "positif" if net > 0.15 else "negatif" if net < -0.15 else "netral"
        out.append(d)
    out.sort(key=lambda d: d["count"], reverse=True)

    return {
        "aspects": out,
        "total": len(items),
        "with_aspect": with_aspect,
        "caveats": [
            "Aspek dideteksi via leksikon kata kunci (lokal, skala jutaan).",
            "Sentimen per-aspek memakai sentimen dokumen — pada komentar campur bisa "
            "kurang presisi, tapi sinyal agregat tetap valid.",
        ],
    }

"""Buzzer / amplifikasi terkoordinasi — deteksi via PERILAKU, bukan follower.

Identifikasi AKUN (pseudonim) yang berperilaku seperti buzzer/amplifier dari sinyal
yang SUDAH ada di database — tanpa data follower/reach (yang terkunci di balik API
berbayar platform sosial). Empat sinyal:

- Repetisi diri  : satu akun memposting konten (near-)identik berulang (copypasta).
- Koordinasi     : konten identik disebar banyak akun berbeda (kampanye serempak).
- Burst timing   : posting menggerombol dalam jendela waktu sangat sempit.
- Volume         : banyak posting (sinyal LEMAH — bisa sekadar pengguna aktif).

Privasi (UU PDP): akun = author_hash (HMAC pseudonim), BUKAN identitas asli. Modul
mengukur POLA, tak pernah mengungkap siapa. Batas jujur: "influencer by reach"
(jangkauan/follower) TIDAK diukur di sini — butuh API platform berbayar. Yang diukur
adalah AMPLIFIKASI PERILAKU (buzzer), bukan popularitas.
"""

from __future__ import annotations

from datetime import datetime

_BURST_WINDOW_S = 300.0  # dua posting < 5 menit dianggap "beruntun" (burst)
_MIN_VOLUME = 3          # akun perlu >=3 posting agar polanya bisa dinilai
_SUSPECT_SCORE = 0.5     # ambang tandai "diduga buzzer"
_CLUSTER_MIN_AUTHORS = 2  # dedup_hash dipakai >=2 akun berbeda → klaster terkoordinasi

# Buzzer = perilaku AKUN sosial/UGC. Platform BERITA/KONTEN dikecualikan: di sana
# "konten identik lintas-akun" = SINDIKASI PERS yang SAH (satu siaran pers BCA muncul
# di banyak portal), BUKAN astroturf. Memasukkannya = false positive (terbukti pada
# data: 62/62 klaster "koordinasi" ternyata rss+news sindikasi).
SOCIAL_PLATFORMS: frozenset[str] = frozenset({
    "telegram", "youtube", "reddit", "x", "x_vendor", "tiktok", "nitter",
    "playstore", "appstore", "apify",
})


def _clamp(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else round(x, 3)


def _burst_factor(timestamps: list[datetime]) -> float:
    """Fraksi jeda antar-posting yang < jendela burst (0..1). <2 posting → 0."""
    ts = sorted(t for t in timestamps if isinstance(t, datetime))
    if len(ts) < 2:
        return 0.0
    bursts = sum(1 for a, b in zip(ts, ts[1:], strict=False) if (b - a).total_seconds() < _BURST_WINDOW_S)
    return bursts / (len(ts) - 1)


def score_accounts(rows: list[dict], top: int = 12) -> dict:
    """rows: [{author, platform, dup, ts, content}] → ranking akun + klaster koordinasi.

    author = author_hash (pseudonim); dup = dedup_hash (None bila tak ada); ts = waktu
    publikasi (None diabaikan utk burst); content = teks (untuk contoh klaster).

    → {accounts:[{account, platform, volume, repetition, coordination, burst,
       buzzer_score, suspect}], clusters:[{authors, posts, sample}], total_accounts,
       suspect_accounts, coordinated_clusters, caveats}.
    """
    # 1) Klaster konten lintas-akun: dup → himpunan author + jumlah posting + contoh teks.
    clusters: dict[str, dict] = {}
    for r in rows:
        dup = r.get("dup")
        if not dup:
            continue
        c = clusters.get(dup)
        if c is None:
            c = clusters[dup] = {"authors": set(), "posts": 0, "sample": None}
        c["authors"].add(r.get("author"))
        c["posts"] += 1
        if c["sample"] is None and r.get("content"):
            c["sample"] = (r["content"] or "")[:180]
    # dup yang benar-benar terkoordinasi (dipakai >=N akun berbeda)
    coordinated_dups = {d for d, c in clusters.items() if len(c["authors"]) >= _CLUSTER_MIN_AUTHORS}

    # 2) Agregasi per akun.
    accts: dict[str, dict] = {}
    for r in rows:
        a = r.get("author")
        if a is None:
            continue
        d = accts.get(a)
        if d is None:
            d = accts[a] = {"platform": r.get("platform"), "volume": 0, "dups": [],
                            "ts": [], "coordinated": 0}
        d["volume"] += 1
        dup = r.get("dup")
        d["dups"].append(dup)
        if r.get("ts") is not None:
            d["ts"].append(r["ts"])
        if dup and dup in coordinated_dups:
            d["coordinated"] += 1

    out = []
    suspects = 0
    for a, d in accts.items():
        vol = d["volume"]
        non_null = [x for x in d["dups"] if x]
        distinct = len(set(non_null))
        repetition = _clamp(1 - distinct / len(non_null)) if non_null else 0.0
        coordination = _clamp(d["coordinated"] / vol) if vol else 0.0
        burst = _clamp(_burst_factor(d["ts"]))
        volume_factor = _clamp((vol - 1) / 19)  # jenuh di ~20 posting
        score = _clamp(0.45 * coordination + 0.30 * repetition + 0.15 * burst + 0.10 * volume_factor)
        suspect = bool(score >= _SUSPECT_SCORE and vol >= _MIN_VOLUME)
        if suspect:
            suspects += 1
        out.append({
            "account": f"#{str(a)[:8]}",  # pseudonim terpotong — tak pernah identitas asli
            "platform": d["platform"],
            "volume": vol,
            "repetition": repetition,
            "coordination": coordination,
            "burst": burst,
            "buzzer_score": score,
            "suspect": suspect,
        })
    out.sort(key=lambda x: (x["buzzer_score"], x["volume"]), reverse=True)

    cl = [
        {"authors": len(c["authors"]), "posts": c["posts"], "sample": c["sample"]}
        for d, c in clusters.items() if d in coordinated_dups
    ]
    cl.sort(key=lambda x: (x["authors"], x["posts"]), reverse=True)

    return {
        "accounts": out[:top],
        "clusters": cl[:8],
        "total_accounts": len(accts),
        "suspect_accounts": suspects,
        "coordinated_clusters": len(cl),
        "caveats": [
            "Akun = pseudonim (author_hash), bukan identitas asli — hanya pola perilaku.",
            "Mengukur AMPLIFIKASI (buzzer), bukan jangkauan/follower — reach butuh API "
            "platform berbayar dan tidak dihitung di sini.",
        ],
    }

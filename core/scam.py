"""Deteksi & label kampanye SCAM/spam — ubah data-cacat jadi INTEL.

Riset (2026-09, bank BCA): 11/14 klaster spam ternyata kampanye scam impersonasi
(investasi bodong "OJK…IZIN RESMI BANK BCA INVESTMENT TRADING", admin palsu "Hai Halo
BCA", lure grup Telegram "Group Telegram Resmi Bank BCA" 791×). Alih-alih hanya
di-dedup diam-diam (lihat [[dedup]]), deteksi ini disurface sebagai TEMUAN bernilai:
brand jadi target phishing/scam — sinyal brand-health & keamanan yang penting.

Klaster spam = konten identik diulang masif (>=MIN_COPIES) dari sedikit akun
(<=MAX_AUTHORS) — pola bot, sama seperti core.dedup — lalu diklasifikasi via signature
leksikon scam Indonesia. Indikatif; verifikasi manual sebelum tindakan.
"""

from __future__ import annotations

import re
from collections import defaultdict

_MIN_COPIES = 5
_MAX_AUTHORS = 2

# tipe scam → (label tampilan, regex signature Indonesia)
_SCAM_SIGNS: dict[str, tuple[str, re.Pattern]] = {
    "investasi_bodong": ("Investasi bodong", re.compile(
        r"\b(investasi|trading|trding|saham|profit|keuntungan|modal|deposit|"
        r"withdraw|bonus|izin resmi|robot forex|binary)\b", re.I)),
    "admin_palsu": ("Admin/CS palsu", re.compile(
        r"\b(hubungi admin|pusat bantuan|hai halo|halo bca|admin resmi|cs resmi|"
        r"customer service resmi|layanan resmi)\b", re.I)),
    "lure_telegram": ("Lure grup Telegram/WA", re.compile(
        r"(grup telegram|group telegram|join grup|link grup|channel resmi|"
        r"t\.me/|wa\.me/|klik link|whatsapp resmi)", re.I)),
    "phishing": ("Phishing/pencurian data", re.compile(
        r"\b(verifikasi|formulir|data pribadi|blokir|nonaktif|segera konfirmasi|"
        r"kode otp|pin atm|link web)\b", re.I)),
}


def detect_scam(rows: list[dict]) -> dict:
    """rows: [{author, dup, content, platform}] → kampanye scam ter-label.

    → {campaigns:[{type,label,messages,accounts,platform,sample}], total_campaigns,
       total_messages, caveats}.
    """
    clusters: dict[str, dict] = defaultdict(
        lambda: {"authors": set(), "n": 0, "sample": None, "platform": None})
    for r in rows:
        d = r.get("dup")
        if not d:
            continue
        c = clusters[d]
        c["authors"].add(r.get("author"))
        c["n"] += 1
        if c["sample"] is None:
            c["sample"] = (r.get("content") or "")[:180]
            c["platform"] = r.get("platform")

    campaigns = []
    total_msg = 0
    for c in clusters.values():
        if c["n"] < _MIN_COPIES or len(c["authors"]) > _MAX_AUTHORS:
            continue  # bukan klaster spam-masif
        text = c["sample"] or ""
        hits = [(k, lbl) for k, (lbl, rx) in _SCAM_SIGNS.items() if rx.search(text)]
        if not hits:
            continue  # spam tapi tak ter-signature scam (mis. sindikasi berita — bukan scam)
        campaigns.append({
            "type": hits[0][0],
            "label": hits[0][1],
            "labels": [lbl for _k, lbl in hits],
            "messages": c["n"],
            "accounts": len(c["authors"]),
            "platform": c["platform"],
            "sample": text,
        })
        total_msg += c["n"]
    campaigns.sort(key=lambda x: x["messages"], reverse=True)

    return {
        "campaigns": campaigns,
        "total_campaigns": len(campaigns),
        "total_messages": total_msg,
        "caveats": [
            "Kampanye = konten scam identik diulang masif (>=5×) dari sedikit akun.",
            "Signature leksikon (investasi/admin/telegram/phishing) — INDIKATIF; "
            "verifikasi manual sebelum tindakan hukum/takedown.",
        ],
    }

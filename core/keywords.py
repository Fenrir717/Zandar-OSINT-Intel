"""Penemuan keyword GROUNDED pada data nyata — bukan tebakan LLM.

Menambang keyword baru dari komentar yang SUDAH terkumpul: hashtag, entitas paling
disebut, dan istilah/bigram menonjol (frekuensi, disaring stopword & seed). Untuk
memperluas scan dengan angle berbeda secara CERDAS — grounded pada apa yang publik
BENAR-BENAR ucapkan, bukan sinonim yang dikarang.

Alur: komentar nyata (+ entitas dari graph) → kandidat berperingkat → analis/planner
memakainya sebagai keyword scan berikutnya (Opsi B: 4x keyword beda, otomatis).
"""

from __future__ import annotations

import re
from collections import Counter

# Stopword Indonesia + partikel umum + noise media sosial. Ringkas tapi menutup yang
# paling sering; keyword yang lolos = istilah bermakna, bukan kata sambung.
_STOP = {
    "yang", "dan", "di", "ke", "dari", "untuk", "pada", "dengan", "ini", "itu", "atau",
    "juga", "akan", "adalah", "apa", "kah", "nya", "aja", "saja", "sudah", "belum",
    "tidak", "tak", "gak", "ga", "ada", "bisa", "kalau", "kalo", "karena", "biar",
    "buat", "kok", "sih", "dong", "deh", "loh", "lah", "banget", "bgt", "udah", "udh",
    "gitu", "gini", "kaya", "kayak", "kek", "mah", "tuh", "nih", "yg", "dgn", "utk",
    "the", "and", "for", "you", "are", "not", "but", "was", "this", "that", "with",
    "http", "https", "www", "com", "amp", "rt", "via", "org", "net", "html",
    "orang", "bikin", "jadi", "lebih", "sama", "punya", "mau", "biasa", "makin",
    "semua", "masih", "malah", "terus", "trus", "pas", "waktu", "hari", "saat",
}
_HASHTAG = re.compile(r"#(\w{2,40})")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")


def _tokens(text: str) -> list[str]:
    """Token kata bermakna (huruf, >=3 char, bukan stopword)."""
    return [w for w in (m.lower() for m in _WORD.findall(text or "")) if w not in _STOP]


def extract_hashtags(comments: list[str], top: int = 15) -> list[tuple[str, int]]:
    c: Counter[str] = Counter()
    for text in comments:
        for h in _HASHTAG.findall(text or ""):
            if h.lower() not in _STOP:
                c[h.lower()] += 1
    return c.most_common(top)


def salient_terms(
    comments: list[str], seed: set[str], top: int = 20, min_count: int = 3
) -> list[tuple[str, int]]:
    """Unigram + bigram paling sering (disaring stopword & seed). Frekuensi mentah —
    murah, skala jutaan; cukup untuk mengangkat istilah dominan yang nyata."""
    uni: Counter[str] = Counter()
    bi: Counter[str] = Counter()
    for text in comments:
        toks = _tokens(text)
        for w in toks:
            if w not in seed:
                uni[w] += 1
        for a, b in zip(toks, toks[1:], strict=False):
            if a not in seed and b not in seed:
                bi[f"{a} {b}"] += 1
    # bigram bermakna (>=min_count) diprioritaskan, lalu unigram
    terms = [(t, n) for t, n in bi.most_common(top) if n >= max(min_count, 3)]
    terms += [(t, n) for t, n in uni.most_common(top) if n >= min_count]
    # dedup jaga urutan
    seen: set[str] = set()
    out: list[tuple[str, int]] = []
    for t, n in terms:
        if t not in seen:
            seen.add(t)
            out.append((t, n))
    return out[:top]


def suggest_keywords(
    comments: list[str], entities: list[dict] | None, seed: list[str], top: int = 15
) -> dict:
    """→ {suggestions:[{keyword, kind, score, count}], total_comments, seed, caveats}.

    kind: hashtag | entitas | frasa. Skor = frekuensi ternormalisasi per jenis
    (hashtag & entitas diberi bobot lebih tinggi — sinyal lebih kuat dari kata biasa).
    """
    seed_l = {s.lower().strip() for s in seed if s and s.strip()}
    total = len(comments)

    cands: dict[str, dict] = {}

    def add(kw: str, kind: str, count: int, weight: float) -> None:
        kw = kw.strip()
        kl = kw.lower()
        if not kw or kl in seed_l or len(kl) < 3:
            return
        sc = round(weight * count, 2)
        cur = cands.get(kl)
        if cur is None or sc > cur["score"]:
            cands[kl] = {"keyword": kw, "kind": kind, "count": count, "score": sc}

    for tag, n in extract_hashtags(comments):
        add(f"#{tag}", "hashtag", n, 2.5)          # hashtag = sinyal topik paling tajam
    for e in (entities or []):
        nm = e.get("name") or ""
        m = int(e.get("mentions") or 0)
        if nm and m >= 3:
            add(nm, "entitas", m, 2.0)             # entitas nyata dari NER/graph
    for term, n in salient_terms(comments, seed_l):
        add(term, "frasa", n, 1.0)                 # istilah/bigram menonjol

    ranked = sorted(cands.values(), key=lambda d: d["score"], reverse=True)[:top]

    return {
        "suggestions": ranked,
        "total_comments": total,
        "seed": seed,
        "caveats": [
            "Keyword ditambang dari komentar NYATA (hashtag/entitas/frasa dominan), "
            "bukan sinonim karangan — grounded pada ucapan publik.",
            "Frekuensi mentah; untuk presisi lebih, saring manual sebelum scan lanjut.",
        ],
    }

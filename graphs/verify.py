"""Graph E — Veracity / Verifikasi Klaim (PRD §7, fase 5).

Alur (README): detect_checkworthy → normalize_claim → retrieve_evidence →
score_sources → verdict. Diimplementasikan padat agar hemat panggilan LLM:

  retrieve_evidence (kode/IO) : tarik bukti OTORITATIF dari sumber ground-truth
                                resmi yang SUDAH terintegrasi (BPS statistik,
                                BMKG kebencanaan) sekali per-run, plus bukti
                                INTERNAL (korpus terkumpul, disiapkan runner).
  score_sources    (kode)     : beri skor kredibilitas per sumber (resmi > sosial).
  assess           (F)        : per narasi, LLM menilai klaim terhadap bukti
                                internal + otoritatif → verdict AVeriTeC, veracity,
                                confidence, rationale. Konservatif ('insufficient'
                                bila bukti tipis). Semua = DRAF (tinjauan analis).
  finalize         (kode)     : kuadran Otentisitas×Kebenaran (healthy/agenda/
                                rumor/operation).

Verdict adalah PENILAIAN AI berstatus draft (ClaimVerdict.review_status), BUKAN
kebenaran final — analis meninjau. Tanpa scraping: hanya sumber resmi terintegrasi
+ korpus sendiri.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from graphs.llm import Usage, get_llm

_MAX_NARRATIVES = 8      # narasi teratas (berisiko) yang diverifikasi per-run
_MAX_AUTH_PER_CLAIM = 3  # item otoritatif paling relevan per klaim ke LLM
_DISASTER_KW = ("gempa", "tsunami", "banjir", "erupsi", "gunung", "bmkg", "cuaca", "bencana")

# Kredibilitas sumber (0..1): resmi > berita > sosial.
_CRED = {"bps": 0.95, "bmkg": 0.95, "ckan": 0.9, "rss": 0.55, "news": 0.6,
         "website": 0.5, "blog": 0.4, "reddit": 0.3, "x": 0.3, "telegram": 0.3, "youtube": 0.35}

_ASSESS_SYSTEM = (
    "Anda analis cek-fakta OSINT. Nilai sebuah KLAIM terhadap BUKTI. Ada dua jenis "
    "bukti: (a) INTERNAL = postingan/berita yang terkumpul dalam investigasi; "
    "(b) OTORITATIF = pernyataan resmi (mis. BPS/BMKG). UTAMAKAN bukti otoritatif. "
    "Balas HANYA JSON {\"check_worthy\": bool, \"claim\": str, \"verdict\": str, "
    "\"veracity\": number, \"confidence\": number, \"rationale\": str}.\n"
    "- verdict ∈ supported|refuted|insufficient|conflicting (taksonomi AVeriTeC).\n"
    "- veracity 0..1 (0 salah .. 1 benar); confidence 0..1.\n"
    "- KONSERVATIF: bila bukti tipis, hanya menegaskan tanpa korroborasi resmi, atau "
    "di luar cakupan bukti → verdict 'insufficient', confidence rendah.\n"
    "- claim: rumuskan ulang klaim inti sebagai kalimat pernyataan Bahasa Indonesia.\n"
    "- rationale: 1-2 kalimat Bahasa Indonesia menyebut dasar penilaian & sumber."
)


class VerifyState(TypedDict, total=False):
    investigation_id: str
    narratives: list[dict]     # {id, label, summary, authenticity, keywords, evidence:[...]}
    bps_pool: list[dict]       # item otoritatif ter-fetch (diisi runner ATAU node)
    fetch_authoritative: bool  # runner set False saat token/koneksi tak ada (uji)
    authoritative: list[dict]  # pool ternormalisasi + kredibilitas
    results: list[dict]
    usage: dict


# ---------------------------------------------------------------- nodes

def _fetch_official(keywords: list[str], disaster: bool) -> list[dict]:
    """Tarik ground-truth resmi (BPS selalu; BMKG bila topik kebencanaan). Tahan-gagal."""
    from workers.adapters import ADAPTERS

    out: list[dict] = []
    plan = [("bps", {"domain": "0000", "keywords": keywords, "max_items": 40})]
    if disaster:
        plan.append(("bmkg", {"feed": "gempaterkini", "max_items": 30}))
    for key, query in plan:
        cls = ADAPTERS.get(key)
        if cls is None:
            continue
        try:
            for item in cls().collect(query):
                out.append({
                    "source": key, "title": item.title, "content": item.content,
                    "url": item.url, "author": item.author,
                    "published_at": item.published_at.isoformat() if item.published_at else None,
                    "credibility": _CRED.get(key, 0.9),
                })
        except Exception:  # noqa: BLE001 — token/koneksi/format → lewati, andalkan internal
            continue
    return out


def _node_retrieve(state: VerifyState) -> dict:
    """retrieve_evidence + score_sources: bukti otoritatif resmi (sekali per-run)."""
    if state.get("bps_pool") is not None:
        return {"authoritative": state.get("bps_pool", [])}  # sudah disiapkan (uji)
    if state.get("fetch_authoritative") is False:
        return {"authoritative": []}
    kws: set[str] = set()
    disaster = False
    for n in state["narratives"]:
        for k in n.get("keywords", []):
            kws.add(k)
        blob = f"{n.get('label', '')} {n.get('summary', '')}".lower()
        if any(d in blob for d in _DISASTER_KW):
            disaster = True
    return {"authoritative": _fetch_official(sorted(kws)[:12], disaster)}


def _relevant(nar: dict, pool: list[dict]) -> list[dict]:
    """Item otoritatif paling relevan dgn narasi (overlap kata kunci)."""
    kws = [k.lower() for k in nar.get("keywords", [])]
    if not kws or not pool:
        return []
    scored = []
    for it in pool:
        text = f"{it.get('title') or ''} {it.get('content') or ''}".lower()
        score = sum(1 for k in kws if k in text)
        if score:
            scored.append((score, it))
    scored.sort(key=lambda t: -t[0])
    return [it for _, it in scored[:_MAX_AUTH_PER_CLAIM]]


def _quadrant(auth: float | None, ver: float | None) -> str | None:
    if auth is None or ver is None:
        return None
    coord, true = auth >= 0.5, ver >= 0.5
    if not coord and true:
        return "healthy"
    if not coord and not true:
        return "rumor"
    if coord and true:
        return "agenda"
    return "operation"


def _node_assess(state: VerifyState) -> dict:
    llm = get_llm()
    usage = Usage(**state.get("usage", {}))
    pool = state.get("authoritative", [])
    results: list[dict] = []
    for nar in state["narratives"][:_MAX_NARRATIVES]:
        internal = nar.get("evidence", [])[:4]
        auth_items = _relevant(nar, pool)
        internal_block = "\n".join(
            f"- ({e.get('platform')}) {(e.get('content') or '')[:200]}" for e in internal
        ) or "(tidak ada)"
        auth_block = "\n".join(
            f"- [{a['source'].upper()}] {(a.get('title') or '')[:80]}: {(a.get('content') or '')[:200]}"
            for a in auth_items
        ) or "(tidak ada sumber otoritatif yang cocok)"

        verdict, veracity, confidence, rationale, claim, worthy = (
            "insufficient", None, 0.2, None, nar.get("label"), True
        )
        try:
            r = llm.call_json(
                "F", _ASSESS_SYSTEM,
                f"NARASI/KLAIM: {nar.get('label')}\nRINGKASAN: {nar.get('summary') or ''}\n\n"
                f"BUKTI INTERNAL:\n{internal_block}\n\nBUKTI OTORITATIF:\n{auth_block}",
                hint={"node": "assess_claim", "narrative_id": nar.get("id")},
            )
            usage.add(r)
            d = r.data if isinstance(r.data, dict) else {}
            worthy = bool(d.get("check_worthy", True))
            claim = str(d.get("claim") or nar.get("label"))[:2000]
            verdict = str(d.get("verdict") or "insufficient").lower().strip()
            if verdict not in ("supported", "refuted", "insufficient", "conflicting"):
                verdict = "insufficient"
            veracity = _num(d.get("veracity"))
            confidence = _num(d.get("confidence")) or 0.3
            rationale = (str(d.get("rationale")).strip() or None) if d.get("rationale") else None
        except Exception:  # noqa: BLE001 — LLM gagal → verdict draf konservatif
            pass

        if verdict == "insufficient":
            veracity = None  # tak bisa tentukan kebenaran → kuadran kosong
        results.append({
            "narrative_id": nar.get("id"),
            "check_worthy": worthy,
            "claim": claim,
            "verdict": verdict,
            "veracity": veracity,
            "confidence": confidence,
            "rationale": rationale,
            "quadrant": _quadrant(nar.get("authenticity"), veracity),
            "authoritative": [
                {"source": a["source"], "title": a.get("title"), "url": a.get("url"),
                 "credibility": a.get("credibility")}
                for a in auth_items
            ],
        })
    return {"results": results, "usage": usage.__dict__}


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, f))


# ---------------------------------------------------------------- build

def build_verifier():
    g = StateGraph(VerifyState)
    g.add_node("retrieve_evidence", _node_retrieve)
    g.add_node("assess", _node_assess)
    g.add_edge(START, "retrieve_evidence")
    g.add_edge("retrieve_evidence", "assess")
    g.add_edge("assess", END)
    return g.compile()


_graph: Any = None


def verifier_graph():
    global _graph
    if _graph is None:
        _graph = build_verifier()
    return _graph


def reset_verifier() -> None:
    global _graph
    _graph = None

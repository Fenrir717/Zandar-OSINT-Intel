"""Graph C — Narrative Analysis (PRD §7, §10).

Alur: cluster → label_narratives → score_risk

  cluster        (kode) : leader-clustering vektor komentar (dari Qdrant) → narasi
  label_narratives (F)  : LLM Tier F melabeli tiap cluster (label + ringkasan)
  score_risk     (kode) : skor risiko dari sinyal nyata (aktor, koordinasi, konten,
                          sebaran) → risk_score + ABC+D (NarrativeAssessment)

I/O (baca Qdrant + Postgres, tulis narratives) ditangani runner async — sama
seperti dispatch di Graph A. Graph ini murni komputasi + LLM, jadi bisa diuji
tanpa DB. Tanpa interrupt: analisis batch, analis meninjau hasil di UI.

Skoring memakai kerangka ABC+D (PRD §10): Actors, Behavior, Content, Distribution
→ authenticity (0 organik .. 1 terkoordinasi). Veracity (benar/salah) DI LUAR
cakupan Graph C — itu tugas Graph E (verifikasi klaim); jadi quadrant ditunda.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from graphs.cluster import cohesion, group_indices, leader_cluster, most_representative
from graphs.llm import Usage, get_llm

# --- kalibrasi (tunable; default disetel untuk multilingual-e5-small) ----------
_COH_FLOOR = 0.75   # cos-sim baseline e5 untuk teks ID acak → dipetakan ke 0
_BURST_HORIZON_H = 24.0  # sebaran waktu cluster <= jam ini dianggap "burst" penuh
_REP_K = 5            # jumlah komentar wakil yang dikirim ke LLM pelabelan
_MAX_LLM_LABELS = 25  # cap panggilan LLM/run: cluster terbesar via LLM, ekor → ekstraktif

_LABEL_SYSTEM = (
    "Anda analis OSINT. Diberi beberapa komentar/berita berpesan serupa, rumuskan "
    "NARASI intinya. WAJIB berbahasa Indonesia. Balas HANYA JSON {label, summary}:\n"
    "- label: frasa ringkas (<=8 kata) yang menangkap KLAIM atau SUDUT PANDANG "
    "narasi (bukan topik umum). Bahasa Indonesia, huruf normal.\n"
    "- summary: satu kalimat Bahasa Indonesia yang netral merangkum pesan kelompok ini.\n"
    "ABAIKAN nama media/outlet, tanggal, byline, dan boilerplate — fokus ke isi pesan."
)


class NarratorState(TypedDict, total=False):
    investigation_id: str
    items: list[dict]        # {comment_id, vector, author_hash, platform, published_at, content, toxicity, sentiment}
    threshold: float
    min_size: int
    clusters: list[list[int]]  # indeks ke items
    narratives: list[dict]
    usage: dict


# ---------------------------------------------------------------- nodes

def _node_cluster(state: NarratorState) -> dict:
    items = state["items"]
    vectors = [it["vector"] for it in items]
    labels = leader_cluster(vectors, state.get("threshold", 0.86))
    min_size = state.get("min_size", 2)
    clusters = [c for c in group_indices(labels) if len(c) >= min_size]
    return {"clusters": clusters}


def _fallback_label(texts: list[str]) -> str:
    """Label ekstraktif (kata paling sering) bila LLM gagal/format aneh."""
    from graphs.llm import _STOP, _WORD

    freq: dict[str, int] = {}
    for t in texts:
        for w in _WORD.findall(t.lower()):
            if w not in _STOP and len(w) > 3:
                freq[w] = freq.get(w, 0) + 1
    top = sorted(freq, key=lambda w: (-freq[w], w))[:4]
    return " ".join(top).title() if top else (texts[0][:40] if texts else "Narasi")


def _node_label(state: NarratorState) -> dict:
    llm = get_llm()
    usage = Usage(**state.get("usage", {}))
    items = state["items"]
    narratives: list[dict] = []
    # clusters sudah terurut besar→kecil; label LLM untuk yang terbesar, ekor ekstraktif
    for rank, idxs in enumerate(state["clusters"]):
        vecs = [items[i]["vector"] for i in idxs]
        rep = [items[idxs[j]]["content"] for j in most_representative(vecs, _REP_K)]
        summary = None
        if rank < _MAX_LLM_LABELS:
            try:
                r = llm.call_json(
                    "F",
                    _LABEL_SYSTEM,
                    "Komentar dalam kelompok:\n- " + "\n- ".join(t[:220] for t in rep),
                    hint={"node": "label_narrative", "texts": rep},
                )
                usage.add(r)
                data = r.data if isinstance(r.data, dict) else {}
                label = str(data.get("label") or "").strip() or _fallback_label(rep)
                summary = data.get("summary") or None
            except Exception:
                label = _fallback_label(rep)  # LLM gagal → ekstraktif; jangan matikan analisis
        else:
            label = _fallback_label(rep)
        narratives.append({"member_idx": idxs, "label": label[:255], "summary": summary})
    return {"narratives": narratives, "usage": usage.__dict__}


def _node_score(state: NarratorState) -> dict:
    items = state["items"]
    narratives = state["narratives"]
    max_size = max((len(n["member_idx"]) for n in narratives), default=1)
    for n in narratives:
        members = [items[i] for i in n["member_idx"]]
        vecs = [m["vector"] for m in members]
        n.update(_score_cluster(members, cohesion(vecs), max_size))
    # Urutkan berdasarkan risiko (tertinggi dulu) untuk penyajian
    narratives.sort(key=lambda n: n["risk_score"], reverse=True)
    return {"narratives": narratives}


# ---------------------------------------------------------------- risk model

def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _parse_dt(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v)
        except ValueError:
            return None
    return None


def _score_cluster(members: list[dict], coh: float, max_size: int) -> dict:
    size = len(members)
    authors = {m.get("author_hash") for m in members}
    unique = len(authors)

    # A — Actors: konsentrasi pengarang (sedikit akun dorong banyak pesan → tinggi)
    actors = (1.0 - unique / size) if size >= 2 else 0.0

    # B — Behavior: koordinasi = kekompakan teks (parafrase/copypasta) + burst waktu
    coh_norm = _clamp((coh - _COH_FLOOR) / (1.0 - _COH_FLOOR))
    times = sorted(t for t in (_parse_dt(m.get("published_at")) for m in members) if t)
    if len(times) >= 2:
        span_h = (times[-1] - times[0]).total_seconds() / 3600.0
        burst = _clamp(1.0 - span_h / _BURST_HORIZON_H)
    else:
        burst = 0.0
    behavior = 0.6 * coh_norm + 0.4 * burst

    # C — Content: bahaya = toksisitas rata-rata + porsi sentimen negatif
    tox = [m["toxicity"] for m in members if m.get("toxicity") is not None]
    mean_tox = sum(tox) / len(tox) if tox else 0.0
    neg_share = sum(1 for m in members if m.get("sentiment") == "neg") / size
    content = _clamp(0.6 * mean_tox + 0.4 * neg_share)

    # D — Distribution: sebaran lintas platform
    platforms = {m.get("platform") for m in members if m.get("platform")}
    distribution = _clamp(len(platforms) / 3.0)

    authenticity = _clamp(0.5 * actors + 0.5 * behavior)  # 0 organik .. 1 terkoordinasi
    size_norm = size / max_size if max_size else 0.0
    risk = _clamp(0.35 * authenticity + 0.30 * content + 0.15 * distribution + 0.20 * size_norm)

    return {
        "size": size,
        "risk_score": round(risk, 4),
        "risk_breakdown": {
            "actors": round(actors, 4), "behavior": round(behavior, 4),
            "content": round(content, 4), "distribution": round(distribution, 4),
            "authenticity": round(authenticity, 4), "cohesion": round(coh, 4),
            "burst": round(burst, 4), "size": size, "unique_authors": unique,
            "mean_toxicity": round(mean_tox, 4), "neg_share": round(neg_share, 4),
            "platforms": sorted(p for p in platforms if p),
        },
        "assessment": {
            "score_actors": round(actors, 4), "score_behavior": round(behavior, 4),
            "score_content": round(content, 4), "score_distribution": round(distribution, 4),
            "authenticity": round(authenticity, 4),
            "veracity": None, "quadrant": None,  # → Graph E (verifikasi klaim)
            "confidence": round(_clamp(size / 10.0, 0.1, 1.0), 4),
        },
        "first_seen": times[0].isoformat() if times else None,
        "last_seen": times[-1].isoformat() if times else None,
    }


# ---------------------------------------------------------------- build

def build_narrator():
    g = StateGraph(NarratorState)
    g.add_node("cluster", _node_cluster)
    g.add_node("label_narratives", _node_label)
    g.add_node("score_risk", _node_score)
    g.add_edge(START, "cluster")
    g.add_edge("cluster", "label_narratives")
    g.add_edge("label_narratives", "score_risk")
    g.add_edge("score_risk", END)
    return g.compile()  # tanpa interrupt → tanpa checkpointer


_graph: Any = None


def narrator_graph():
    global _graph
    if _graph is None:
        _graph = build_narrator()
    return _graph


def reset_narrator() -> None:
    global _graph
    _graph = None

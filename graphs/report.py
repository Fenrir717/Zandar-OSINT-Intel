"""Graph D — Report (PRD §7, fase 4): laporan intelijen BER-SITASI.

Alur: outline → write_section (map, RAG) → verify_citations → assemble

  outline          (kode) : kerangka bagian tetap (ringkasan, narasi berisiko,
                            koordinasi/CIB, rekomendasi) — deterministik, tahan-banting.
  write_section    (F)    : LLM menulis tiap bagian dalam Bahasa Indonesia DENGAN
                            sitasi [n] ke daftar sumber (bukti nyata dari investigasi).
                            Gagal → fallback ekstraktif dari ringkasan narasi.
  verify_citations (kode) : buang sitasi [n] yang mengarah ke indeks tak-ada
                            (anti-halusinasi) → hanya sumber nyata yang tersisa.
  assemble         (kode) : rakit judul + bagian + daftar sumber (URL) → laporan final.

Graph murni komputasi + LLM (tanpa DB/IO). Runner async menyiapkan input
(narasi + bukti dari Postgres) dan menyimpan hasil (MinIO + baris Report).

Sitasi mengacu ke SUMBER NYATA (URL bukti) — inilah inti "ber-sitasi": tiap
klaim dalam laporan dapat ditelusuri balik ke postingan/artikel aslinya.
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from graphs.llm import Usage, get_llm

_MAX_NARRATIVES = 12   # narasi teratas (berisiko) yang masuk laporan
_MAX_EV_PER_NAR = 3    # bukti wakil per narasi untuk konteks LLM
_CITE = re.compile(r"\[(\d+)\]")

_SECTION_SYSTEM = (
    "Anda analis intelijen OSINT menulis LAPORAN resmi. WAJIB Bahasa Indonesia, "
    "nada objektif dan ringkas. Anda diberi DAFTAR SUMBER bernomor. Tulis bagian "
    "yang diminta (1-3 paragraf) dan DUKUNG tiap klaim penting dengan sitasi [n] "
    "yang mengacu ke nomor sumber tersebut. JANGAN mengarang sumber di luar daftar. "
    "JANGAN memakai nomor sumber yang tidak ada. Balas HANYA JSON {\"body\": \"...\"}."
)

# Kerangka bagian tetap (id, judul, instruksi penulisan).
_OUTLINE: list[dict[str, str]] = [
    {"id": "ringkasan", "heading": "Ringkasan Eksekutif",
     "brief": "Rangkum temuan utama investigasi: berapa narasi menonjol, tingkat "
              "risiko/koordinasi keseluruhan, dan implikasinya. Padat, untuk pimpinan."},
    {"id": "narasi", "heading": "Narasi Berisiko",
     "brief": "Uraikan narasi paling berisiko satu per satu: klaim/sudut pandangnya, "
              "mengapa berisiko (aktor/konten/sebaran), dengan sitasi ke sumber."},
    {"id": "koordinasi", "heading": "Indikasi Koordinasi (CIB)",
     "brief": "Nilai tanda perilaku tak-otentik terkoordinasi: konsentrasi aktor, "
              "keserempakan (burst), kekompakan pesan (copypasta), sebaran lintas kanal."},
    {"id": "rekomendasi", "heading": "Rekomendasi",
     "brief": "Beri langkah tindak lanjut yang proporsional dan dapat dijalankan "
              "(pemantauan, verifikasi klaim, pra-bantahan). Hindari klaim berlebih."},
]


class ReportState(TypedDict, total=False):
    investigation_id: str
    title: str
    narratives: list[dict]   # {label, summary, risk_score, risk_breakdown, evidence:[{content,url,platform,published_at}]}
    stats: dict
    sources: list[dict]      # {n, url, platform, snippet, narrative} — daftar sitasi global
    outline: list[dict]
    sections: list[dict]     # {id, heading, body}
    citations: list[dict]    # sumber yang benar-benar dikutip
    report: dict             # dokumen akhir (assemble)
    usage: dict


# ---------------------------------------------------------------- nodes

def _node_outline(state: ReportState) -> dict:
    """Bangun kerangka + daftar sumber global (bukti nyata per narasi)."""
    nars = state["narratives"][:_MAX_NARRATIVES]
    sources: list[dict] = []
    seen: set[str] = set()
    for nar in nars:
        for ev in (nar.get("evidence") or [])[:_MAX_EV_PER_NAR]:
            url = ev.get("url")
            key = url or f"{ev.get('platform')}:{(ev.get('content') or '')[:40]}"
            if key in seen:
                continue
            seen.add(key)
            sources.append({
                "n": len(sources) + 1,
                "url": url,
                "platform": ev.get("platform"),
                "published_at": ev.get("published_at"),
                "snippet": (ev.get("content") or "")[:160],
                "narrative": nar.get("label"),
            })
    return {"outline": _OUTLINE, "sources": sources}


def _sources_block(sources: list[dict]) -> str:
    lines = []
    for s in sources:
        tag = s.get("narrative") or ""
        lines.append(f"[{s['n']}] ({s.get('platform') or '?'}) {s['snippet']}  — narasi: {tag}")
    return "\n".join(lines) if lines else "(tidak ada sumber)"


def _narratives_block(nars: list[dict]) -> str:
    lines = []
    for i, n in enumerate(nars, 1):
        rb = n.get("risk_breakdown") or {}
        lines.append(
            f"{i}. {n.get('label')} — risiko {n.get('risk_score')}; "
            f"otentisitas {rb.get('authenticity')}, aktor {rb.get('actors')}, "
            f"konten {rb.get('content')}, sebaran {rb.get('distribution')}. "
            f"{n.get('summary') or ''}"
        )
    return "\n".join(lines)


def _fallback_body(section_id: str, nars: list[dict], stats: dict) -> str:
    """Isi bagian ekstraktif bila LLM gagal — deterministik, tetap ber-sitasi via narasi."""
    if section_id == "ringkasan":
        n = len(nars)
        hi = sum(1 for x in nars if (x.get("risk_score") or 0) >= 0.5)
        cov = stats.get("coverage")
        return (
            f"Investigasi mengidentifikasi {n} narasi menonjol, {hi} di antaranya "
            f"berisiko tinggi (skor ≥ 0,5). Cakupan analisis "
            f"{round((cov or 0) * 100)}% komentar terklasifikasi. Rincian dan bukti "
            "pendukung diuraikan pada bagian berikut."
        )
    if section_id == "narasi":
        parts = [f"- {n.get('label')} (risiko {n.get('risk_score')}): {n.get('summary') or ''}"
                 for n in nars[:6]]
        return "Narasi paling berisiko:\n" + "\n".join(parts)
    if section_id == "koordinasi":
        coord = [n for n in nars if ((n.get('risk_breakdown') or {}).get('authenticity') or 0) >= 0.6]
        return (
            f"{len(coord)} narasi menunjukkan indikasi koordinasi (otentisitas ≥ 0,6): "
            "konsentrasi aktor dan/atau kekompakan pesan yang tinggi. Perlu telaah "
            "lanjut untuk memastikan perilaku tak-otentik terkoordinasi."
        )
    return (
        "Direkomendasikan pemantauan berkelanjutan atas narasi berisiko tinggi, "
        "verifikasi klaim faktual pada kanal terdampak, dan penyiapan pra-bantahan "
        "berbasis bukti bila eskalasi berlanjut."
    )


def _node_write(state: ReportState) -> dict:
    llm = get_llm()
    usage = Usage(**state.get("usage", {}))
    nars = state["narratives"][:_MAX_NARRATIVES]
    stats = state.get("stats", {})
    sources = state.get("sources", [])
    src_block = _sources_block(sources)
    nar_block = _narratives_block(nars)

    sections: list[dict] = []
    for sec in state["outline"]:
        body = None
        try:
            r = llm.call_json(
                "F",
                _SECTION_SYSTEM,
                f"BAGIAN: {sec['heading']}\nTUGAS: {sec['brief']}\n\n"
                f"RINGKASAN NARASI:\n{nar_block}\n\n"
                f"DAFTAR SUMBER (untuk sitasi [n]):\n{src_block}",
                hint={"node": "write_section", "section": sec["id"]},
            )
            usage.add(r)
            data = r.data if isinstance(r.data, dict) else {}
            body = str(data.get("body") or "").strip() or None
        except Exception:
            body = None
        if not body:
            body = _fallback_body(sec["id"], nars, stats)
        sections.append({"id": sec["id"], "heading": sec["heading"], "body": body})
    return {"sections": sections, "usage": usage.__dict__}


def _node_verify(state: ReportState) -> dict:
    """Buang sitasi [n] yang mengacu ke sumber tak-ada; kumpulkan sumber yang dikutip."""
    sources = state.get("sources", [])
    valid = {s["n"] for s in sources}
    used: set[int] = set()
    for sec in state["sections"]:
        def _keep(m: re.Match) -> str:
            n = int(m.group(1))
            if n in valid:
                used.add(n)
                return m.group(0)
            return ""  # halusinasi → hapus token
        sec["body"] = _CITE.sub(_keep, sec["body"]).replace("  ", " ").strip()
    citations = [s for s in sources if s["n"] in used]
    return {"sections": state["sections"], "citations": citations}


def _node_assemble(state: ReportState) -> dict:
    """Rakit dokumen akhir (dict siap-simpan)."""
    doc = {
        "title": state.get("title") or "Laporan Intelijen",
        "sections": [{"heading": s["heading"], "body": s["body"]} for s in state["sections"]],
        "citations": [
            {"n": c["n"], "url": c.get("url"), "platform": c.get("platform"),
             "published_at": c.get("published_at"), "snippet": c.get("snippet")}
            for c in state.get("citations", [])
        ],
        "meta": {
            "narratives": len(state["narratives"]),
            "cited_sources": len(state.get("citations", [])),
        },
    }
    return {"report": doc}


# ---------------------------------------------------------------- build

def build_reporter():
    g = StateGraph(ReportState)
    g.add_node("outline", _node_outline)
    g.add_node("write_section", _node_write)
    g.add_node("verify_citations", _node_verify)
    g.add_node("assemble", _node_assemble)
    g.add_edge(START, "outline")
    g.add_edge("outline", "write_section")
    g.add_edge("write_section", "verify_citations")
    g.add_edge("verify_citations", "assemble")
    g.add_edge("assemble", END)
    return g.compile()


_graph: Any = None


def reporter_graph():
    global _graph
    if _graph is None:
        _graph = build_reporter()
    return _graph


def reset_reporter() -> None:
    global _graph
    _graph = None

"""Graph A — Intelligence Planner (PRD §7).

Alur: parse_intent → expand_keywords → select_sources → estimate_cost →
      human_approval [interrupt] → (approve → dispatch | reject → END)

parse_intent/select_sources = Tier R; expand_keywords = Tier F; estimate_cost &
dispatch = kode. human_approval memakai LangGraph interrupt(): graph tersuspensi,
analis approve/edit/reject via API, lalu graph dilanjutkan.

Checkpointer: MemorySaver (dalam-proses). PostgresSaver = upgrade produksi
(bertahan restart) — sama seperti indobert untuk klasifikasi. State plan juga
dicerminkan ke agent_runs sehingga terlihat walau proses restart.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from graphs.llm import Usage, get_llm
from workers.adapters import ADAPTERS, describe_all

# Kapabilitas koleksi per adapter (untuk memandu select_sources):
#  keyword-OK  = produktif hanya dengan keywords (tanpa URL/target)
#  butuh-URL   = perlu base_url/feeds/urls konkret → jangan dipilih untuk scan keyword-only
_KEYWORD_CAPABLE = {"rss", "news", "reddit", "youtube", "playstore", "appstore", "telegram"}
_NEEDS_TARGET = {"blog", "website", "sitemap", "forum", "nitter", "satudata", "ckan"}


def _source_catalog() -> str:
    """Katalog adapter untuk prompt select_sources — LLM harus memilih dari kunci ini.
    Ditandai kapabilitas + ketersediaan kredensial (biar plan hanya berisi sumber
    yang benar-benar bisa mengumpulkan)."""
    from core.config import get_settings

    s = get_settings()
    cred_ok = {
        "youtube": bool(getattr(s, "youtube_api_key", "")),
        "github": bool(getattr(s, "github_token", "")),
        "telegram": bool(getattr(s, "telegram_bot_token", "")),
        "x": bool(getattr(s, "x_bearer_token", "")),
    }
    lines = []
    for a in describe_all():
        k = a["key"]
        flags = []
        if a["tier"] != "free":
            flags.append(a["tier"])
        if a["requires_credentials"]:
            flags.append("kredensial-OK" if cred_ok.get(k) else "kredensial-BELUM")
        if k in _KEYWORD_CAPABLE:
            flags.append("keyword-OK")
        elif k in _NEEDS_TARGET:
            flags.append("butuh-URL")
        tag = f" [{', '.join(flags)}]" if flags else ""
        note = a["rate_note"] or a["legal_note"]
        lines.append(f"- {k}{tag}: {note[:60]}")
    return "\n".join(lines)


class PlannerState(TypedDict, total=False):
    investigation_id: str
    query: str
    data_policy: str
    budget_cap_usd: float | None
    intent: dict
    keywords: list[str]
    sources: list[dict]
    cost: dict
    decision: str  # approve | reject | edit
    edited_sources: list[dict] | None
    dispatched: list[str]
    usage: dict  # {tokens_in, tokens_out, calls}


# Estimasi biaya/volume per platform (kasar; disempurnakan saat provider nyata masuk)
_COST_PER_ITEM = {"news": 0.0, "rss": 0.0, "youtube": 0.0, "reddit": 0.0, "telegram": 0.0,
                  "blog": 0.0, "website": 0.0, "forum": 0.0, "github": 0.0,
                  "x": 0.005, "tiktok": 0.002}


def _node_parse_intent(state: PlannerState) -> dict:
    llm = get_llm()
    usage = Usage(**state.get("usage", {}))
    r = llm.call_json(
        "R",
        "Ekstrak sasaran investigasi OSINT dari query analis menjadi JSON: "
        "topic, actors, region, period_days, languages, keywords_seed.",
        state["query"],
        hint={"node": "parse_intent", "query": state["query"]},
    )
    usage.add(r)
    return {"intent": r.data, "usage": usage.__dict__}


def _node_expand_keywords(state: PlannerState) -> dict:
    llm = get_llm()
    usage = Usage(**state["usage"])
    seed = state["intent"].get("keywords_seed", [])
    r = llm.call_json(
        "F",
        "Perluas kata kunci: sinonim, slang Indonesia, ejaan alternatif, hashtag. JSON {keywords}.",
        f"seed: {seed}",
        hint={"node": "expand_keywords", "keywords_seed": seed},
    )
    usage.add(r)
    kws = r.data.get("keywords") or seed
    return {"keywords": kws, "usage": usage.__dict__}


def _node_select_sources(state: PlannerState) -> dict:
    llm = get_llm()
    usage = Usage(**state["usage"])
    system = (
        "Pilih sumber koleksi OSINT. WAJIB pilih HANYA dari daftar 'platform' berikut "
        "(pakai kunci persis apa adanya).\n"
        "ATURAN untuk scan berbasis KEYWORD (tanpa URL target dari analis):\n"
        "- Pilih HANYA sumber bertanda [keyword-OK]: rss, news, reddit, youtube, playstore.\n"
        "- Untuk analisis REPUTASI/brand, playstore (review aplikasi) sangat relevan.\n"
        "- JANGAN pilih sumber [butuh-URL] (blog/website/forum/nitter) — tak ada target.\n"
        "- JANGAN pilih sumber [kredensial-BELUM]; boleh pilih [kredensial-OK] (mis. youtube).\n"
        "- Query tiap sumber cukup {keywords,timespan}. youtube, reddit & playstore JUGA "
        "pakai {keywords} (bukan video_ids/subreddits/app_ids). fetch_full_text:true untuk news.\n\n"
        f"PLATFORM TERSEDIA:\n{_source_catalog()}\n\n"
        'Balas JSON: {"sources":[{"platform":"<kunci>","query":{"keywords":[...],"timespan":"90d"},"est_items":<int>}]}'
    )
    r = llm.call_json(
        "R",
        system,
        f"keywords: {state['keywords']}, region: {state['intent'].get('region')}, "
        f"period_days: {state['intent'].get('period_days')}",
        hint={"node": "select_sources", "keywords": state["keywords"]},
    )
    usage.add(r)
    # Validasi keras: hanya kunci yang dikenal registry (buang halusinasi platform)
    sources = [s for s in r.data.get("sources", []) if s.get("platform") in ADAPTERS]
    return {"sources": sources, "usage": usage.__dict__}


def _node_recon(state: PlannerState) -> dict:
    """Agen Recon (agent intel): temukan URL target relevan (DuckDuckGo + benih LLM)
    → tambah sumber `website` agar wacana web umum (blog/artikel/forum) ikut terkumpul
    tanpa analis mengetik URL. Best-effort — kegagalan tak menghentikan perencanaan."""
    sources = list(state.get("sources", []))
    keywords = state.get("keywords", [])
    topic = (state.get("intent") or {}).get("topic", "")
    try:
        from graphs.recon import discover_targets

        found = discover_targets(keywords, topic=topic)
    except Exception:
        found = []
    for spec in found:
        if spec["platform"] == "website":
            existing = next((s for s in sources if s.get("platform") == "website"), None)
            if existing:  # gabungkan bila LLM sudah memilih website
                merged = list(dict.fromkeys(
                    list(existing.get("query", {}).get("urls", [])) + spec["query"]["urls"]))
                existing.setdefault("query", {})["urls"] = merged
                existing["est_items"] = len(merged)
            else:
                sources.append(spec)
        else:  # sitemap (media ID) dsb — tambah, dedup per (platform,url)
            url = spec.get("query", {}).get("url")
            if not any(s.get("platform") == spec["platform"]
                       and s.get("query", {}).get("url") == url for s in sources):
                sources.append(spec)
    return {"sources": sources}


def _node_estimate_cost(state: PlannerState) -> dict:
    """Node kode (tanpa LLM): estimasi volume & biaya, validasi budget cap."""
    total_items = sum(int(s.get("est_items", 0)) for s in state["sources"])
    est_cost = sum(int(s.get("est_items", 0)) * _COST_PER_ITEM.get(s["platform"], 0.0) for s in state["sources"])
    cap = state.get("budget_cap_usd")
    within = cap is None or est_cost <= float(cap)
    return {"cost": {"est_items": total_items, "est_cost_usd": round(est_cost, 2), "within_budget": within}}


def _node_human_approval(state: PlannerState) -> dict:
    """Suspend graph. API mengembalikan rencana ke analis; resume dgn keputusan."""
    decision = interrupt({
        "intent": state["intent"],
        "keywords": state["keywords"],
        "sources": state["sources"],
        "cost": state["cost"],
    })
    # decision bisa string ('approve'/'reject') atau dict {decision, edited_sources}
    if isinstance(decision, dict):
        return {"decision": decision.get("decision", "reject"), "edited_sources": decision.get("edited_sources")}
    return {"decision": str(decision)}


def _route_after_approval(state: PlannerState) -> str:
    return "dispatch" if state.get("decision") == "approve" else END


def _node_dispatch(state: PlannerState) -> dict:
    """Node kode: buat Collection + CollectionRun untuk tiap sumber yang disetujui,
    lalu enqueue collect_source. Dijalankan async oleh runner."""
    # Implementasi DB dilakukan runner (butuh sesi async); di sini hanya menandai
    # sumber final yang akan didispatch.
    final = state.get("edited_sources") or state["sources"]
    return {"sources": final, "dispatched": ["__pending__"]}


def build_planner():
    g = StateGraph(PlannerState)
    g.add_node("parse_intent", _node_parse_intent)
    g.add_node("expand_keywords", _node_expand_keywords)
    g.add_node("select_sources", _node_select_sources)
    g.add_node("recon", _node_recon)
    g.add_node("estimate_cost", _node_estimate_cost)
    g.add_node("human_approval", _node_human_approval)
    g.add_node("dispatch", _node_dispatch)

    g.add_edge(START, "parse_intent")
    g.add_edge("parse_intent", "expand_keywords")
    g.add_edge("expand_keywords", "select_sources")
    g.add_edge("select_sources", "recon")
    g.add_edge("recon", "estimate_cost")
    g.add_edge("estimate_cost", "human_approval")
    g.add_conditional_edges("human_approval", _route_after_approval, {"dispatch": "dispatch", END: END})
    g.add_edge("dispatch", END)

    return g.compile(checkpointer=MemorySaver())


# Singleton graph (checkpointer MemorySaver hidup selama proses API)
_graph: Any = None


def planner_graph():
    global _graph
    if _graph is None:
        _graph = build_planner()
    return _graph

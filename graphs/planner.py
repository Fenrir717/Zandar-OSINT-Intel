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
from workers.adapters import ADAPTERS


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
    r = llm.call_json(
        "R",
        "Pilih sumber koleksi + parameter dari registry. Hindari sumber berbayar/berkredensial "
        "kecuali diminta. JSON {sources:[{platform,query,est_items}]}.",
        f"keywords: {state['keywords']}, region: {state['intent'].get('region')}",
        hint={"node": "select_sources", "keywords": state["keywords"]},
    )
    usage.add(r)
    # Validasi: hanya platform yang dikenal registry
    sources = [s for s in r.data.get("sources", []) if s.get("platform") in ADAPTERS]
    return {"sources": sources, "usage": usage.__dict__}


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
    g.add_node("estimate_cost", _node_estimate_cost)
    g.add_node("human_approval", _node_human_approval)
    g.add_node("dispatch", _node_dispatch)

    g.add_edge(START, "parse_intent")
    g.add_edge("parse_intent", "expand_keywords")
    g.add_edge("expand_keywords", "select_sources")
    g.add_edge("select_sources", "estimate_cost")
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

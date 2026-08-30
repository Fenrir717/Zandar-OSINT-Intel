"""Uji Graph A (planner) — topologi, interrupt/resume, estimasi biaya.
Memakai provider LLM stub + graph fresh per test (MemorySaver bersih). Tanpa DB.
"""

import pytest
from langgraph.types import Command

from graphs.llm import StubProvider
from graphs.planner import _node_estimate_cost, build_planner


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    """Isolasi: paksa provider stub apa pun isi .env (mesin dev bisa set groq)."""
    from core.config import get_settings
    from graphs.llm import reset_llm

    monkeypatch.setenv("LLM_PROVIDER", "stub")
    get_settings.cache_clear()
    reset_llm()
    yield
    get_settings.cache_clear()
    reset_llm()


def _run_to_interrupt(query: str, budget: float | None = 25.0):
    g = build_planner()
    cfg = {"configurable": {"thread_id": "t-" + query[:8]}}
    init = {"investigation_id": "x", "query": query, "data_policy": "local_only",
            "budget_cap_usd": budget, "usage": {}}
    res = g.invoke(init, cfg)
    return g, cfg, res


def test_graph_interrupts_at_approval() -> None:
    _, _, res = _run_to_interrupt("sentimen soal kenaikan harga BBM subsidi")
    intr = res.get("__interrupt__")
    assert intr, "graph harus tersuspensi di human_approval"
    plan = intr[0].value
    assert "intent" in plan and "keywords" in plan and "sources" in plan and "cost" in plan


def test_plan_selects_known_sources() -> None:
    _, _, res = _run_to_interrupt("narasi hoaks pemilu di media sosial")
    plan = res["__interrupt__"][0].value
    platforms = [s["platform"] for s in plan["sources"]]
    assert platforms and all(p in ("news", "rss") for p in platforms)  # stub pilih free-tier


def test_approve_resumes_and_marks_dispatch() -> None:
    g, cfg, _ = _run_to_interrupt("isu korupsi bansos")
    res = g.invoke(Command(resume={"decision": "approve", "edited_sources": None}), cfg)
    assert res["decision"] == "approve"
    assert res.get("dispatched") == ["__pending__"]
    assert res["sources"]


def test_reject_resumes_without_dispatch() -> None:
    g, cfg, _ = _run_to_interrupt("topik sensitif X")
    res = g.invoke(Command(resume={"decision": "reject", "edited_sources": None}), cfg)
    assert res["decision"] == "reject"
    assert "dispatched" not in res  # node dispatch tidak dijalankan


def test_edited_sources_override_on_approve() -> None:
    g, cfg, _ = _run_to_interrupt("uji edit sumber")
    edited = [{"platform": "reddit", "query": {"subreddits": ["indonesia"]}, "est_items": 50}]
    res = g.invoke(Command(resume={"decision": "approve", "edited_sources": edited}), cfg)
    assert [s["platform"] for s in res["sources"]] == ["reddit"]


def test_estimate_cost_within_budget() -> None:
    out = _node_estimate_cost({
        "sources": [{"platform": "news", "est_items": 200}, {"platform": "rss", "est_items": 100}],
        "budget_cap_usd": 25.0,
    })
    assert out["cost"]["est_items"] == 300
    assert out["cost"]["est_cost_usd"] == 0.0
    assert out["cost"]["within_budget"] is True


def test_estimate_cost_over_budget_metered() -> None:
    # X berbayar ~$0.005/item; 10rb item = $50 > budget $25
    out = _node_estimate_cost({
        "sources": [{"platform": "x", "est_items": 10000}],
        "budget_cap_usd": 25.0,
    })
    assert out["cost"]["est_cost_usd"] == 50.0
    assert out["cost"]["within_budget"] is False


def test_stub_deterministic() -> None:
    p = StubProvider()
    a = p.call_json("R", "s", "u", hint={"node": "parse_intent", "query": "harga beras naik"})
    b = p.call_json("R", "s", "u", hint={"node": "parse_intent", "query": "harga beras naik"})
    assert a.data == b.data
    assert a.tokens_in > 0

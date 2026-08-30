"""Uji Graph C (narrator) — clustering → label → skor risiko. Stub LLM, tanpa DB/Qdrant."""

import math

import pytest

from graphs.narrator import build_narrator


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    from core.config import get_settings
    from graphs.llm import reset_llm

    monkeypatch.setenv("LLM_PROVIDER", "stub")
    get_settings.cache_clear()
    reset_llm()
    yield
    get_settings.cache_clear()
    reset_llm()


def _n(v):
    m = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / m for x in v]


def _item(cid, vec, author, sent, tox, platform, when):
    return {"comment_id": cid, "vector": _n(vec), "author_hash": author,
            "platform": platform, "published_at": when, "content": f"komentar {cid}",
            "toxicity": tox, "sentiment": sent}


def _items():
    return [
        # Grup A — terkoordinasi: 1 akun, teks nyaris identik, toksik, burst waktu
        _item("a1", [1, 0.01, 0, 0], "acc-1", "neg", 0.8, "rss", "2026-01-01T00:00:00"),
        _item("a2", [1, 0, 0.01, 0], "acc-1", "neg", 0.9, "rss", "2026-01-01T00:05:00"),
        _item("a3", [1, 0.01, 0.01, 0], "acc-1", "neg", 0.7, "rss", "2026-01-01T00:10:00"),
        # Grup B — organik: 2 akun berbeda, netral, low-tox, tersebar berhari-hari
        _item("b1", [0, 1, 0, 0.01], "acc-2", "neu", 0.1, "news", "2026-01-01T00:00:00"),
        _item("b2", [0, 1, 0.01, 0], "acc-3", "neu", 0.05, "news", "2026-01-05T00:00:00"),
        # Singleton → tersaring min_size
        _item("c1", [0, 0, 1, 0], "acc-4", "pos", 0.0, "youtube", "2026-01-02T00:00:00"),
    ]


def _run(min_size=2):
    g = build_narrator()
    return g.invoke({"items": _items(), "threshold": 0.84, "min_size": min_size}, {})


def test_two_narratives_singleton_filtered() -> None:
    res = _run()
    nars = res["narratives"]
    assert len(nars) == 2  # dua cluster >= min_size; singleton dibuang
    assert {n["size"] for n in nars} == {3, 2}


def test_sorted_by_risk_coordinated_first() -> None:
    nars = _run()["narratives"]
    assert nars[0]["risk_score"] >= nars[1]["risk_score"]
    top = nars[0]
    assert top["size"] == 3  # grup terkoordinasi/toksik = risiko tertinggi


def test_coordination_signals() -> None:
    nars = _run()["narratives"]
    a = next(n for n in nars if n["size"] == 3)
    b = next(n for n in nars if n["size"] == 2)
    # 1 akun untuk 3 komentar → konsentrasi aktor tinggi; 2 akun → 0
    assert a["risk_breakdown"]["actors"] > b["risk_breakdown"]["actors"]
    assert a["risk_breakdown"]["unique_authors"] == 1
    assert a["assessment"]["authenticity"] > b["assessment"]["authenticity"]


def test_content_and_breakdown_shape() -> None:
    a = next(n for n in _run()["narratives"] if n["size"] == 3)
    bd = a["risk_breakdown"]
    for k in ("actors", "behavior", "content", "distribution", "authenticity", "cohesion"):
        assert 0.0 <= bd[k] <= 1.0
    assert bd["mean_toxicity"] > 0.5  # grup toksik
    assert a["assessment"]["veracity"] is None      # veracity = tugas Graph E
    assert a["assessment"]["quadrant"] is None


def test_label_present() -> None:
    for n in _run()["narratives"]:
        assert n["label"] and isinstance(n["label"], str)


def test_min_size_one_keeps_singleton() -> None:
    nars = _run(min_size=1)["narratives"]
    assert len(nars) == 3  # termasuk singleton


def test_extract_json_salvages_list() -> None:
    # gpt-oss kadang balas [{...}] alih-alih {...} — harus diselamatkan, bukan crash
    from graphs.llm import _extract_json

    assert _extract_json('[{"label": "X", "summary": "y"}]') == {"label": "X", "summary": "y"}
    assert _extract_json('["a", "b"]') == {}      # list tanpa dict → kosong
    assert _extract_json("bukan json") == {}


def test_fallback_label_from_keywords() -> None:
    from graphs.narrator import _fallback_label

    lab = _fallback_label(["harga beras naik terus", "beras makin mahal harga"])
    assert "Beras" in lab or "Harga" in lab  # kata dominan jadi label


def test_label_survives_llm_error(monkeypatch) -> None:
    """LLM error saat pelabelan → fallback ekstraktif; analisis tetap jalan."""
    import graphs.narrator as N

    class _Boom:
        def call_json(self, *a, **k):
            raise RuntimeError("semua model gagal")

    monkeypatch.setattr(N, "get_llm", lambda: _Boom())
    nars = build_narrator().invoke({"items": _items(), "threshold": 0.84, "min_size": 2}, {})["narratives"]
    assert len(nars) == 2  # tetap menghasilkan narasi
    assert all(n["label"] for n in nars)  # label ekstraktif terisi

"""Uji embedder stub — deterministik, tanpa key/model/Qdrant."""

import math

from workers.embed.stub import StubEmbedder


def test_stub_dim_and_count() -> None:
    e = StubEmbedder()
    vecs = e.embed(["halo", "dunia", "tiga"])
    assert len(vecs) == 3
    assert all(len(v) == e.dim for v in vecs)


def test_stub_deterministic() -> None:
    e = StubEmbedder()
    assert e.embed(["harga bbm naik"]) == e.embed(["harga bbm naik"])


def test_stub_l2_normalized() -> None:
    e = StubEmbedder()
    v = e.embed(["stimulus pangan"])[0]
    norm = math.sqrt(sum(x * x for x in v))
    assert abs(norm - 1.0) < 1e-6  # siap cosine


def test_stub_different_text_different_vector() -> None:
    e = StubEmbedder()
    a = e.embed(["positif sekali"])[0]
    b = e.embed(["negatif sekali"])[0]
    assert a != b


def test_empty() -> None:
    assert StubEmbedder().embed([]) == []

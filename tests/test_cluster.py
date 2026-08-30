"""Uji leader-clustering pure-Python (tanpa numpy/DB)."""

import math

from graphs.cluster import (
    centroid,
    cohesion,
    group_indices,
    leader_cluster,
    most_representative,
)


def _n(v: list[float]) -> list[float]:
    m = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / m for x in v]


def test_identical_vectors_one_cluster() -> None:
    v = _n([1.0, 2.0, 3.0])
    labels = leader_cluster([v, v, v], threshold=0.9)
    assert labels == [0, 0, 0]


def test_orthogonal_vectors_separate() -> None:
    a, b, c = _n([1, 0, 0]), _n([0, 1, 0]), _n([0, 0, 1])
    labels = leader_cluster([a, b, c], threshold=0.5)
    assert len(set(labels)) == 3


def test_threshold_controls_merge() -> None:
    a = _n([1, 0, 0, 0])
    near = _n([1, 0.05, 0, 0])   # cos ~0.9987 dgn a
    far = _n([0, 1, 0, 0])       # cos 0 dgn a
    labels = leader_cluster([a, near, far], threshold=0.84)
    assert labels[0] == labels[1]      # a & near menyatu
    assert labels[2] != labels[0]      # far terpisah


def test_group_indices_orders_by_size() -> None:
    # dua di cluster 0, satu di cluster 1 → cluster besar didahulukan
    groups = group_indices([1, 0, 0])
    assert groups[0] == [1, 2]
    assert groups[1] == [0]


def test_centroid_and_cohesion() -> None:
    v = _n([1, 1, 0])
    c = centroid([v, v])
    assert abs(cohesion([v, v], c) - 1.0) < 1e-9  # identik → kompak sempurna


def test_most_representative_prefers_centroid() -> None:
    a = _n([1, 0, 0])
    dup = _n([1, 0.01, 0])
    outlier = _n([0.2, 1, 0])
    rep = most_representative([a, dup, outlier], k=2)
    assert 2 not in rep  # outlier bukan wakil terbaik

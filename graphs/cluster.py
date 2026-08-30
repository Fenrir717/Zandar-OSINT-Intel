"""Leader (threshold) clustering pure-Python untuk vektor L2-ternormalisasi.

Tanpa numpy/sklearn → jalan di base install (embedder stub/gemini/local, tanpa
extra [ml]). Untuk vektor ternormalisasi, cosine = dot product.

Cocok untuk forensik narasi: greedy leader clustering mengelompokkan pesan
SANGAT-mirip (parafrase/copypasta) — persis sinyal koordinasi (CIB) yang dicari,
bukan sekadar topik longgar. Deterministik: urutan input menentukan pembentukan
cluster, jadi pemanggil harus mengurutkan input secara stabil.
"""

from __future__ import annotations

import math


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def leader_cluster(vectors: list[list[float]], threshold: float) -> list[int]:
    """Algoritma leader (Hartigan): kembalikan label cluster (int) per vektor.

    Vektor diasumsikan L2-normal. Tiap vektor bergabung ke cluster dengan LEADER
    (anggota pertama, tetap) termirip bila cos-sim >= threshold; jika tidak,
    menjadi leader cluster baru. Leader tetap (bukan centroid bergeser) → radius
    tegas di sekitar tiap seed, menghindari absorpsi ke blob raksasa dan cocok
    untuk mendeteksi pesan berulang/terkoordinasi. Deterministik pada urutan input.
    """
    leaders: list[list[float]] = []  # vektor perwakilan (anggota pertama tiap cluster)
    labels: list[int] = []
    for v in vectors:
        best, best_sim = -1, -1.0
        for ci, lead in enumerate(leaders):
            s = _dot(v, lead)
            if s > best_sim:
                best_sim, best = s, ci
        if best >= 0 and best_sim >= threshold:
            labels.append(best)
        else:
            leaders.append(v)
            labels.append(len(leaders) - 1)
    return labels


def group_indices(labels: list[int]) -> list[list[int]]:
    """Kelompokkan indeks per label → daftar cluster, terurut (besar→kecil, lalu label)."""
    groups: dict[int, list[int]] = {}
    for i, lab in enumerate(labels):
        groups.setdefault(lab, []).append(i)
    return [g for _, g in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))]


def centroid(vectors: list[list[float]]) -> list[float]:
    """Centroid ternormalisasi dari sekumpulan vektor (rata-rata → L2)."""
    if not vectors:
        return []
    acc = [0.0] * len(vectors[0])
    for v in vectors:
        for i, x in enumerate(v):
            acc[i] += x
    return _normalize(acc)


def cohesion(vectors: list[list[float]], cent: list[float] | None = None) -> float:
    """Rata-rata cos-sim anggota ke centroid (kekompakan cluster; 0..1)."""
    if not vectors:
        return 0.0
    c = cent if cent is not None else centroid(vectors)
    return sum(_dot(v, c) for v in vectors) / len(vectors)


def most_representative(vectors: list[list[float]], k: int) -> list[int]:
    """Indeks k vektor termirip ke centroid (contoh wakil untuk pelabelan)."""
    if not vectors:
        return []
    c = centroid(vectors)
    order = sorted(range(len(vectors)), key=lambda i: _dot(vectors[i], c), reverse=True)
    return order[:k]

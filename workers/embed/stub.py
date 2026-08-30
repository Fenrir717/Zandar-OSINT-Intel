"""Embedder stub — vektor deterministik dari hash teks (tanpa key/model).

Untuk menguji plumbing (embed → Qdrant upsert → search) tanpa dependensi. BUKAN
semantik nyata: teks identik → vektor identik, tapi kedekatan tak bermakna. Ganti
ke gemini/local untuk pencarian semantik sungguhan.
"""

import hashlib
import math

from workers.embed.base import Embedder

_DIM = 256


class StubEmbedder(Embedder):
    version = "stub-256"
    dim = _DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        # Perluas hash jadi vektor dim, lalu normalisasi L2 (cosine-ready)
        vec: list[float] = []
        seed = text.encode("utf-8")
        counter = 0
        while len(vec) < _DIM:
            h = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
            vec.extend(b / 255.0 - 0.5 for b in h)
            counter += 1
        vec = vec[:_DIM]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

"""Kontrak embedder. Semua provider mengembalikan vektor per teks."""

from abc import ABC, abstractmethod


class Embedder(ABC):
    version: str
    dim: int  # dimensi vektor — harus konsisten (koleksi Qdrant dibuat dgn dim ini)

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Kembalikan satu vektor float per teks (panjang == len(texts))."""
        raise NotImplementedError

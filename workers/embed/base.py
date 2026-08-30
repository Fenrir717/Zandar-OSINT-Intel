"""Kontrak embedder. Semua provider mengembalikan vektor per teks."""

from abc import ABC, abstractmethod


class Embedder(ABC):
    version: str
    dim: int  # dimensi vektor — harus konsisten (koleksi Qdrant dibuat dgn dim ini)

    @abstractmethod
    def embed(self, texts: list[str], kind: str = "passage") -> list[list[float]]:
        """Kembalikan satu vektor float per teks (panjang == len(texts)).

        kind: 'passage' (dokumen yang diindeks) | 'query' (teks pencarian).
        Model asimetris (mis. e5, Gemini retrieval) memakainya; lainnya abaikan.
        """
        raise NotImplementedError

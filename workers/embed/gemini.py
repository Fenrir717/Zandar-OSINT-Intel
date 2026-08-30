"""Embedder Gemini — API embedding Google GRATIS (endpoint NATIVE).

Free tier berbasis token yang longgar — menyelesaikan dilema BGE-M3-vs-4GB (tanpa
beban lokal). Butuh GEMINI_API_KEY (aistudio.google.com).

Memakai endpoint NATIVE (batchEmbedContents) + header x-goog-api-key — bukan
OpenAI-compat/Bearer (yang menolak key format baru). Model gemini-embedding-001
mendukung Matryoshka: outputDimensionality kecil (768) lalu di-normalisasi ulang.
"""

import math
import time

import httpx

from core.config import get_settings
from workers.embed.base import Embedder

BASE = "https://generativelanguage.googleapis.com/v1beta"
_DEFAULT_MODEL = "gemini-embedding-001"
_OUT_DIM = 768  # MRL truncation (dari 3072) — hemat storage/speed di Qdrant
_BATCH = 20  # free tier RPM/TPM rendah — batch kecil
_MAX_CHARS = 2000  # cukup untuk semantik; hemat token


class GeminiEmbedder(Embedder):
    def __init__(self) -> None:
        s = get_settings()
        self.key = s.gemini_api_key
        if not self.key:
            raise RuntimeError("EMBED_PROVIDER=gemini tapi GEMINI_API_KEY kosong (aistudio.google.com).")
        self.model = s.embed_model or _DEFAULT_MODEL
        self.dim = _OUT_DIM
        self.version = f"gemini:{self.model}:{_OUT_DIM}"

    def embed(self, texts: list[str], kind: str = "passage") -> list[list[float]]:
        if not texts:
            return []
        task = "RETRIEVAL_QUERY" if kind == "query" else "RETRIEVAL_DOCUMENT"
        out: list[list[float]] = []
        for i in range(0, len(texts), _BATCH):
            batch = [t[:_MAX_CHARS] for t in texts[i : i + _BATCH]]
            out.extend(self._embed_batch(batch, task))
        return out

    def _embed_batch(self, batch: list[str], task: str) -> list[list[float]]:
        payload = {
            "requests": [
                {"model": f"models/{self.model}", "content": {"parts": [{"text": t}]},
                 "taskType": task, "outputDimensionality": _OUT_DIM}
                for t in batch
            ]
        }
        delay = 2.0
        for _attempt in range(5):
            resp = httpx.post(
                f"{BASE}/models/{self.model}:batchEmbedContents",
                headers={"x-goog-api-key": self.key}, json=payload, timeout=120,
            )
            if resp.status_code == 429:  # rate limit free tier → backoff
                time.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            resp.raise_for_status()
            return [_normalize(e.get("values", [])) for e in resp.json().get("embeddings", [])]
        raise RuntimeError("Gemini embedding: rate limit terus (429) setelah 5 percobaan")


def _normalize(vec: list[float]) -> list[float]:
    # MRL truncation perlu re-normalisasi L2 (cosine-ready)
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]

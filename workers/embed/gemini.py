"""Embedder Gemini — API embedding Google GRATIS (endpoint OpenAI-compatible).

Free tier berbasis token yang longgar (~jutaan token/menit) — menyelesaikan dilema
BGE-M3-vs-4GB: tanpa beban lokal. Butuh GEMINI_API_KEY (daftar aistudio.google.com).
Model default text-embedding-004 (dim 768).
"""

import httpx

from core.config import get_settings
from workers.embed.base import Embedder

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/openai/embeddings"
_DEFAULT_MODEL = "text-embedding-004"
_DIM = {"text-embedding-004": 768, "gemini-embedding-001": 3072}


class GeminiEmbedder(Embedder):
    def __init__(self) -> None:
        s = get_settings()
        self.key = s.gemini_api_key
        if not self.key:
            raise RuntimeError("EMBED_PROVIDER=gemini tapi GEMINI_API_KEY kosong (aistudio.google.com).")
        self.model = s.embed_model or _DEFAULT_MODEL
        self.dim = _DIM.get(self.model, 768)
        self.version = f"gemini:{self.model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = httpx.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {self.key}"},
            json={"model": self.model, "input": list(texts)},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        # Urutan respons OpenAI-compat mengikuti index; urutkan untuk aman
        data.sort(key=lambda d: d.get("index", 0))
        return [d["embedding"] for d in data]

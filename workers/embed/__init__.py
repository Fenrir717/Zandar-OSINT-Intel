"""Provider embedding (Fase 2) — swappable seperti classifier/LLM.

  stub   — deterministik dari hash teks, tanpa key/model (uji plumbing Qdrant)
  gemini — Google Gemini embedding GRATIS (token-based longgar); menyelesaikan
           dilema BGE-M3-vs-4GB (tanpa beban lokal). Butuh GEMINI_API_KEY.
  local  — model ringan lokal (e5-small) untuk investigasi data_policy=local_only

Pilih via EMBED_PROVIDER.
"""

from core.config import get_settings
from workers.embed.base import Embedder
from workers.embed.stub import StubEmbedder

_instance: Embedder | None = None


def get_embedder() -> Embedder:
    global _instance
    if _instance is None:
        name = get_settings().embed_provider
        if name == "stub":
            _instance = StubEmbedder()
        elif name == "gemini":
            from workers.embed.gemini import GeminiEmbedder

            _instance = GeminiEmbedder()
        elif name == "local":
            from workers.embed.local import LocalEmbedder

            _instance = LocalEmbedder()
        else:
            raise ValueError(f"EMBED_PROVIDER tidak dikenal: {name} (stub|gemini|local)")
    return _instance


def reset_embedder() -> None:
    global _instance
    _instance = None


__all__ = ["Embedder", "get_embedder", "reset_embedder"]

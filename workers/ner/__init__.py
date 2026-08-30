"""NER lokal (Fase 3) — ekstraksi entitas dari komentar untuk knowledge graph."""

from workers.ner.extract import Entity, NerExtractor

_instance: NerExtractor | None = None


def get_ner() -> NerExtractor:
    """Singleton — muat model NER sekali per proses worker."""
    global _instance
    if _instance is None:
        _instance = NerExtractor()
    return _instance


__all__ = ["Entity", "NerExtractor", "get_ner"]

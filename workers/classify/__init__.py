"""Provider klasifikasi (Tier L, PRD §7.4) — pola swappable seperti adapter koleksi.

Default 'lexicon' berjalan tanpa dependensi berat/GPU sehingga backend Fase 2 langsung
hidup. 'indobert' (impor lazy torch/transformers) menyusul sebagai jalur produksi;
'flash' (LLM API) sebagai alternatif bake-off. Pilih via env CLASSIFIER_PROVIDER.
"""

from core.config import get_settings
from workers.classify.base import Classifier, Label
from workers.classify.lexicon import LexiconClassifier

_REGISTRY: dict[str, type[Classifier]] = {"lexicon": LexiconClassifier}


def _load_indobert() -> type[Classifier]:
    from workers.classify.indobert import IndoBertClassifier  # impor lazy (butuh torch)

    return IndoBertClassifier


def _load_flash() -> type[Classifier]:
    from workers.classify.flash import FlashClassifier  # impor lazy (butuh LLM_PROVIDER)

    return FlashClassifier


_LAZY = {"indobert": _load_indobert, "flash": _load_flash}
_instance: Classifier | None = None


def get_classifier() -> Classifier:
    """Kembalikan instance classifier singleton sesuai CLASSIFIER_PROVIDER."""
    global _instance
    if _instance is None:
        name = get_settings().classifier_provider
        if name in _REGISTRY:
            cls = _REGISTRY[name]
        elif name in _LAZY:
            cls = _LAZY[name]()
        else:
            raise ValueError(f"CLASSIFIER_PROVIDER tidak dikenal: {name}")
        _instance = cls()
    return _instance


__all__ = ["Classifier", "Label", "get_classifier"]

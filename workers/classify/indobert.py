"""Provider IndoBERT (Tier L, jalur produksi). Impor torch/transformers LAZY —
modul ini tidak dimuat kecuali CLASSIFIER_PROVIDER=indobert, sehingga backend tetap
hidup tanpa dependensi berat.

HIBRIDA: RoBERTa fine-tuned Indonesia untuk SENTIMEN (dimensi terpenting, terbukti
menangkap nuansa yang leksikon lewatkan), + leksikon untuk emosi/intent/toksisitas
(head khusus model menyusul). Jadi mengganti lexicon→indobert adalah upgrade murni.

Muat di GPU bila ada (fp16, cocok RTX 3050 4GB untuk inferensi), fallback CPU.
Model dipilih via env; unduh sekali dari HuggingFace lalu di-cache lokal.
"""

from workers.classify.base import Classifier, Label
from workers.classify.lexicon import LexiconClassifier

# Peta label model sentimen Indonesia populer → skema internal
_SENT_MAP = {
    "positive": ("pos", 0.7), "negative": ("neg", -0.7), "neutral": ("neu", 0.0),
    "LABEL_0": ("neg", -0.7), "LABEL_1": ("neu", 0.0), "LABEL_2": ("pos", 0.7),
}


class IndoBertClassifier(Classifier):
    version = "indobert-v1"

    def __init__(self) -> None:
        try:
            import torch
            from transformers import pipeline
        except ImportError as exc:  # pragma: no cover - hanya bila ml extra belum dipasang
            raise RuntimeError(
                "Provider indobert butuh torch+transformers. Pasang: pip install -e \".[ml]\" "
                "lalu set CLASSIFIER_PROVIDER=indobert."
            ) from exc

        from core.config import get_settings

        model = get_settings().indobert_sentiment_model
        device = 0 if torch.cuda.is_available() else -1
        self._device = "cuda" if device == 0 else "cpu"
        dtype = torch.float16 if device == 0 else torch.float32
        self._pipe = pipeline(
            "text-classification", model=model, device=device, dtype=dtype, truncation=True,
        )
        self._lex = LexiconClassifier()  # untuk emosi/intent/toksisitas
        self.version = f"indobert-sent+lex[{self._device}]"  # <=50 char (kolom model_version)

    def classify(self, texts: list[str]) -> list[Label]:
        texts = list(texts)
        raw = self._pipe(texts, batch_size=32)  # pipeline batching internal
        lex = self._lex.classify(texts)  # emosi/intent/toksisitas dari leksikon
        out: list[Label] = []
        for r, lx in zip(raw, lex, strict=True):
            sentiment, score = _SENT_MAP.get(r["label"], ("neu", 0.0))
            conf = float(r.get("score", 0.5))
            out.append(
                Label(
                    sentiment=sentiment,
                    sentiment_score=round(score * conf, 3),
                    emotion=lx.emotion,
                    intent=lx.intent,
                    toxicity=lx.toxicity,
                    model_version=self.version,
                )
            )
        return out

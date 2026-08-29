"""Provider IndoBERT (Tier L, jalur produksi). Impor torch/transformers LAZY —
modul ini tidak dimuat kecuali CLASSIFIER_PROVIDER=indobert, sehingga backend tetap
hidup tanpa dependensi berat.

Jalur pemakaian (setelah `pip install -e ".[ml]"` dan model ter-unduh):
- Sentimen: model fine-tuned Indonesia (mis. w11wo/indonesian-roberta-base-sentiment-classifier)
- Emosi/intent: model terpisah atau head multi-task (menyusul; sementara diturunkan dari sentimen)

Muat di GPU bila ada (fp16, cocok RTX 3050 4GB untuk inferensi), fallback CPU.
Model dipilih via env; unduh sekali dari HuggingFace lalu di-cache lokal.
"""

from workers.classify.base import Classifier, Label

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
        dtype = torch.float16 if device == 0 else torch.float32
        self._pipe = pipeline(
            "text-classification", model=model, device=device, torch_dtype=dtype, truncation=True,
        )
        self.version = f"indobert:{model.split('/')[-1]}"

    def classify(self, texts: list[str]) -> list[Label]:
        # transformers pipeline melakukan batching internal
        raw = self._pipe(list(texts), batch_size=32)
        out: list[Label] = []
        for r in raw:
            sentiment, score = _SENT_MAP.get(r["label"], ("neu", 0.0))
            conf = float(r.get("score", 0.5))
            signed = round(score * conf, 3)
            out.append(
                Label(
                    sentiment=sentiment,
                    sentiment_score=signed,
                    emotion={"pos": "joy", "neg": "anger", "neu": "neutral"}.get(sentiment, "neutral"),
                    intent="informational",  # head intent terpisah menyusul
                    toxicity=0.0,  # model toksisitas terpisah menyusul
                    model_version=self.version,
                )
            )
        return out

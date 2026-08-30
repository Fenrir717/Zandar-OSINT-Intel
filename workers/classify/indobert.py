"""Provider IndoBERT MULTI-MODEL (Tier L, jalur produksi). Impor torch/transformers
LAZY — modul ini tidak dimuat kecuali CLASSIFIER_PROVIDER=indobert.

Tiga model RoBERTa Indonesia (keluarga w11wo + CNERG) + leksikon untuk intent:
- Sentimen : w11wo/indonesian-roberta-base-sentiment-classifier
- Emosi    : w11wo/indonesian-roberta-base-prdect-id (5 emosi)
- Toksisitas: Hate-speech-CNERG/dehatebert-mono-indonesian (skor hate)
- Intent   : leksikon (tak ada taksonomi OSINT siap-pakai)

Tiap sub-model dimuat try/except; bila gagal (jaringan/OOM) → fallback leksikon
untuk dimensi itu. Muat di GPU bila ada (fp16, RTX 3050), fallback CPU.
"""

from workers.classify.base import Classifier, Label
from workers.classify.lexicon import LexiconClassifier

_SENT_MAP = {
    "positive": ("pos", 0.7), "negative": ("neg", -0.7), "neutral": ("neu", 0.0),
    "LABEL_0": ("neg", -0.7), "LABEL_1": ("neu", 0.0), "LABEL_2": ("pos", 0.7),
}
# PRDECT-ID → taksonomi internal EMOTIONS
_EMO_MAP = {
    "anger": "anger", "fear": "fear", "happy": "joy", "love": "trust", "sadness": "sadness",
    "joy": "joy", "sad": "sadness", "trust": "trust", "surprise": "surprise", "disgust": "disgust",
}


class IndoBertClassifier(Classifier):
    version = "indobert-multi"

    def __init__(self) -> None:
        try:
            import torch
            from transformers import pipeline
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                'Provider indobert butuh torch+transformers. Pasang: pip install -e ".[ml]"'
            ) from exc

        from core.config import get_settings

        s = get_settings()
        device = 0 if torch.cuda.is_available() else -1
        self._dev = "cuda" if device == 0 else "cpu"
        dtype = torch.float16 if device == 0 else torch.float32

        def _load(model_id: str, **kw):
            # Coba cache dulu (local_files_only=True) agar tak hang cek-update ke HF
            # saat jaringan flaky; baru online bila model belum ter-cache.
            for local_only in (True, False):
                try:
                    return pipeline("text-classification", model=model_id, device=device,
                                    dtype=dtype, truncation=True, local_files_only=local_only, **kw)
                except Exception:
                    continue
            return None  # gagal offline & online → dimensi ini fallback leksikon

        self._sent = _load(s.indobert_sentiment_model)
        self._emo = _load(s.indobert_emotion_model)
        self._tox = _load(s.indobert_hatespeech_model, top_k=None)  # semua skor
        self._lex = LexiconClassifier()

        active = [n for n, m in (("sent", self._sent), ("emo", self._emo), ("tox", self._tox)) if m]
        self.version = f"indobert-multi[{'+'.join(active) or 'none'}/{self._dev}]"[:50]

    def classify(self, texts: list[str]) -> list[Label]:
        texts = list(texts)
        lex = self._lex.classify(texts)
        sent = self._sent(texts, batch_size=32) if self._sent else None
        emo = self._emo(texts, batch_size=32) if self._emo else None
        tox = self._tox(texts, batch_size=32) if self._tox else None

        out: list[Label] = []
        for i, lx in enumerate(lex):
            if sent:
                s_lbl, s_score = _SENT_MAP.get(sent[i]["label"], ("neu", 0.0))
                conf = float(sent[i].get("score", 0.5))  # keyakinan model (0..1)
                sentiment = s_lbl
                sentiment_score = round(s_score * conf, 3)
            else:
                sentiment, sentiment_score = lx.sentiment, lx.sentiment_score
                conf = min(1.0, abs(lx.sentiment_score) + 0.3)  # proxy keyakinan leksikon

            emotion = _EMO_MAP.get(emo[i]["label"].lower(), "neutral") if emo else lx.emotion
            toxicity = _hate_score(tox[i]) if tox else lx.toxicity

            out.append(Label(
                sentiment=sentiment, sentiment_score=sentiment_score,
                emotion=emotion, intent=lx.intent, toxicity=toxicity,
                model_version=self.version, confidence=round(conf, 3),
            ))
        return out


def _hate_score(scores) -> float:
    """dehatebert: cari probabilitas label 'hate' (atau LABEL_1) dari daftar skor."""
    if isinstance(scores, dict):
        scores = [scores]
    for s in scores:
        lbl = str(s.get("label", "")).lower()
        if ("hate" in lbl and "non" not in lbl) or lbl in ("label_1", "abusive", "toxic"):
            return round(float(s.get("score", 0.0)), 3)
    return 0.0

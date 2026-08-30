"""Classifier 'flash' — via LLM (Tier F) untuk bake-off vs IndoBERT (PRD §7.4).

Mengklasifikasi BATCH komentar dalam satu panggilan LLM (hemat panggilan) memakai
infra graphs.llm (provider + rantai fallback + retry yang sama). Butuh LLM_PROVIDER
nyata (mis. openrouter/groq); dengan 'stub' hasilnya netral (tak berguna untuk eval).

Bukan jalur produksi default (lokal/privasi → IndoBERT). Gunanya membandingkan
akurasi & biaya IndoBERT lokal vs LLM API pada gold set berlabel manusia.
"""

from workers.classify.base import EMOTIONS, INTENTS, SENTIMENTS, Classifier, Label

_BATCH = 12
_MAX_CHARS = 400
_SCORE = {"pos": 0.6, "neg": -0.6, "neu": 0.0, "mixed": 0.0}

_SYSTEM = (
    "Anda pengklasifikasi komentar publik Bahasa Indonesia. Untuk SETIAP komentar "
    "bernomor, tentukan:\n"
    "- sentiment: pos | neg | neu | mixed\n"
    "- emotion: anger | fear | joy | sadness | trust | surprise | disgust | neutral\n"
    "- intent: informational | opinion | question | criticism | support | spam | threat\n"
    "- toxicity: angka 0..1 (0=sopan, 1=sangat kasar/kebencian)\n"
    'Balas HANYA JSON: {"results":[{"i":0,"sentiment":"...","emotion":"...",'
    '"intent":"...","toxicity":0.0}, ...]} — satu objek per komentar, urut sesuai nomor i.'
)


class FlashClassifier(Classifier):
    def __init__(self) -> None:
        from core.config import get_settings
        from graphs.llm import get_llm

        self.llm = get_llm()
        self.version = f"flash:{get_settings().llm_provider}"

    def classify(self, texts: list[str]) -> list[Label]:
        out: list[Label] = []
        for i in range(0, len(texts), _BATCH):
            out.extend(self._classify_batch(texts[i : i + _BATCH]))
        return out

    def _classify_batch(self, batch: list[str]) -> list[Label]:
        numbered = "\n".join(f"{j}. {t[:_MAX_CHARS]}" for j, t in enumerate(batch))
        try:
            r = self.llm.call_json("F", _SYSTEM, numbered, hint={"node": "classify"})
            data = r.data if isinstance(r.data, dict) else {}
        except Exception:
            data = {}
        results = data.get("results") if isinstance(data.get("results"), list) else []
        by_i: dict[int, dict] = {}
        for k, x in enumerate(results):
            if isinstance(x, dict):
                try:
                    by_i[int(x.get("i", k))] = x
                except (TypeError, ValueError):
                    by_i[k] = x
        return [self._to_label(by_i.get(k, {})) for k in range(len(batch))]

    def _to_label(self, x: dict) -> Label:
        sent = x.get("sentiment") if x.get("sentiment") in SENTIMENTS else "neu"
        emo = x.get("emotion") if x.get("emotion") in EMOTIONS else "neutral"
        intent = x.get("intent") if x.get("intent") in INTENTS else "informational"
        try:
            tox = max(0.0, min(1.0, float(x.get("toxicity", 0) or 0)))
        except (TypeError, ValueError):
            tox = 0.0
        return Label(
            sentiment=sent, sentiment_score=_SCORE.get(sent, 0.0),
            emotion=emo, intent=intent, toxicity=round(tox, 3), model_version=self.version,
        )

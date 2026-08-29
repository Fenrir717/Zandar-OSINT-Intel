"""Baseline leksikon Bahasa Indonesia — deterministik, tanpa dependensi, jalan di CPU.

Ini BASELINE (model_version 'lexicon-v0'), bukan target akhir. Fungsinya membuat
pipeline Fase 2 hidup end-to-end sekarang; IndoBERT menggantikannya setelah bake-off
gold set (PRD §7.4). Menangani negasi ("tidak bagus" → negatif) dan penguat.
"""

import re

from workers.classify.base import Classifier, Label

POSITIVE = {
    "bagus", "baik", "hebat", "mantap", "keren", "suka", "senang", "puas", "terbaik",
    "sukses", "berhasil", "untung", "menang", "cinta", "sayang", "indah", "nyaman",
    "murah", "cepat", "ramah", "membantu", "bermanfaat", "adil", "jujur", "aman",
    "setuju", "dukung", "mendukung", "apresiasi", "terima kasih", "salut", "bangga",
    "harapan", "optimis", "damai", "lancar", "efektif", "cair", "naik", "tumbuh",
}
NEGATIVE = {
    "buruk", "jelek", "parah", "gagal", "rugi", "kalah", "benci", "kecewa", "marah",
    "sedih", "takut", "khawatir", "cemas", "mahal", "lambat", "lelet", "korupsi",
    "korup", "bohong", "tipu", "curang", "kacau", "hancur", "rusak", "bahaya",
    "masalah", "krisis", "turun", "anjlok", "susah", "sulit", "miskin", "menderita",
    "protes", "tolak", "menolak", "kritik", "salah", "dosa", "jahat", "licik",
    "oligarki", "represif", "otoriter", "diskriminasi", "ketidakadilan", "hoaks",
}
TOXIC = {"anjing", "bangsat", "goblok", "tolol", "bodoh", "kampret", "bajingan", "brengsek", "keparat", "sialan"}
NEGATORS = {"tidak", "tak", "bukan", "belum", "jangan", "kurang", "gak", "ga", "nggak", "enggak"}
INTENSIFIERS = {"sangat", "banget", "amat", "sekali", "terlalu", "paling"}

EMOTION_HINTS = {
    "anger": {"marah", "geram", "kesal", "murka", "benci", "korupsi", "curang", "protes"},
    "fear": {"takut", "khawatir", "cemas", "ngeri", "bahaya", "krisis", "ancaman"},
    "joy": {"senang", "gembira", "bahagia", "suka", "puas", "mantap", "syukur"},
    "sadness": {"sedih", "kecewa", "menderita", "duka", "prihatin"},
    "trust": {"percaya", "yakin", "dukung", "harapan", "optimis", "jujur"},
    "surprise": {"kaget", "terkejut", "heran", "wow", "tak nyangka"},
    "disgust": {"jijik", "muak", "najis", "menjijikkan"},
}
_WORD = re.compile(r"[a-zA-Z]+")


class LexiconClassifier(Classifier):
    version = "lexicon-v0"

    def classify(self, texts: list[str]) -> list[Label]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> Label:
        tokens = _WORD.findall(text.lower())
        pos = neg = 0.0
        tox = 0
        for i, tok in enumerate(tokens):
            weight = 1.0
            if i > 0 and tokens[i - 1] in INTENSIFIERS:
                weight = 1.5
            negated = i > 0 and tokens[i - 1] in NEGATORS
            if tok in POSITIVE:
                if negated:
                    neg += weight
                else:
                    pos += weight
            elif tok in NEGATIVE:
                if negated:
                    pos += weight
                else:
                    neg += weight
            if tok in TOXIC:
                tox += 1

        total = pos + neg
        score = 0.0 if total == 0 else round((pos - neg) / total, 3)
        if total == 0:
            sentiment = "neu"
        elif pos > 0 and neg > 0 and min(pos, neg) / max(pos, neg) > 0.5:
            sentiment = "mixed"
        elif score > 0.15:
            sentiment = "pos"
        elif score < -0.15:
            sentiment = "neg"
        else:
            sentiment = "neu"

        toxicity = round(min(1.0, tox / 3), 3)
        return Label(
            sentiment=sentiment,
            sentiment_score=score,
            emotion=self._emotion(tokens, sentiment),
            intent=self._intent(text, tokens),
            toxicity=toxicity,
            model_version=self.version,
        )

    def _emotion(self, tokens: list[str], sentiment: str) -> str:
        counts = {emo: sum(1 for t in tokens if t in words) for emo, words in EMOTION_HINTS.items()}
        best = max(counts, key=lambda k: counts[k])
        if counts[best] > 0:
            return best
        return {"pos": "joy", "neg": "anger", "mixed": "surprise"}.get(sentiment, "neutral")

    def _intent(self, text: str, tokens: list[str]) -> str:
        tset = set(tokens)
        if "?" in text or tset & {"apakah", "kenapa", "mengapa", "bagaimana", "kapan", "siapa"}:
            return "question"
        if tset & {"anjing", "bangsat", "goblok", "kampret"}:
            return "spam" if len(tokens) < 4 else "criticism"
        if tset & {"kritik", "protes", "tolak", "menolak", "seharusnya", "harusnya", "korupsi"}:
            return "criticism"
        if tset & {"dukung", "mendukung", "setuju", "semangat", "maju"}:
            return "support"
        if tset & {"menurut", "rasanya", "mungkin", "sepertinya", "harusnya"}:
            return "opinion"
        return "informational"

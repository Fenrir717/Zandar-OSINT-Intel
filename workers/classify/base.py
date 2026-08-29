"""Kontrak classifier. Semua provider mengembalikan Label per teks."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

SENTIMENTS = ("pos", "neg", "neu", "mixed")
EMOTIONS = ("anger", "fear", "joy", "sadness", "trust", "surprise", "disgust", "neutral")
INTENTS = ("informational", "opinion", "question", "criticism", "support", "spam", "threat")


@dataclass
class Label:
    sentiment: str  # pos|neg|neu|mixed
    sentiment_score: float  # -1..1
    emotion: str
    intent: str
    toxicity: float  # 0..1
    model_version: str


class Classifier(ABC):
    """Provider klasifikasi batch. `classify` menerima banyak teks agar provider
    berbasis model (IndoBERT/LLM) bisa memanfaatkan batching."""

    version: str

    @abstractmethod
    def classify(self, texts: list[str]) -> list[Label]:
        raise NotImplementedError

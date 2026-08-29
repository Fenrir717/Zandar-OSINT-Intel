"""Uji baseline leksikon — deterministik, tanpa DB/model."""

from workers.classify.base import EMOTIONS, INTENTS, SENTIMENTS
from workers.classify.lexicon import LexiconClassifier

clf = LexiconClassifier()


def one(text: str):
    return clf.classify([text])[0]


def test_positive() -> None:
    lab = one("Pelayanannya bagus banget, saya sangat puas dan senang")
    assert lab.sentiment == "pos"
    assert lab.sentiment_score > 0


def test_negative() -> None:
    lab = one("Programnya gagal parah, korupsi di mana-mana, mengecewakan")
    assert lab.sentiment == "neg"
    assert lab.sentiment_score < 0


def test_negation_flips_polarity() -> None:
    # "tidak bagus" harus dibaca negatif, bukan positif
    lab = one("pelayanannya tidak bagus")
    assert lab.sentiment == "neg"


def test_neutral_when_no_sentiment_words() -> None:
    lab = one("Rapat dijadwalkan pada hari Senin pukul sepuluh")
    assert lab.sentiment == "neu"
    assert lab.sentiment_score == 0.0


def test_question_intent() -> None:
    assert one("Kapan bantuan ini akan cair?").intent == "question"


def test_toxicity_detected() -> None:
    lab = one("dasar goblok tolol bangsat")
    assert lab.toxicity > 0


def test_labels_in_valid_domains() -> None:
    lab = one("Harga beras naik terus tapi kualitas menurun, saya kecewa")
    assert lab.sentiment in SENTIMENTS
    assert lab.emotion in EMOTIONS
    assert lab.intent in INTENTS
    assert lab.model_version == "lexicon-v0"


def test_batch_matches_singles() -> None:
    texts = ["bagus sekali", "parah dan gagal", "rapat hari senin"]
    batch = clf.classify(texts)
    assert len(batch) == 3
    assert [b.sentiment for b in batch] == ["pos", "neg", "neu"]


def test_deterministic() -> None:
    t = "korupsi bikin rakyat menderita dan marah"
    assert clf.classify([t])[0].sentiment == clf.classify([t])[0].sentiment

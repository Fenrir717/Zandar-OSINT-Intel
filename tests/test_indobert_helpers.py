"""Uji helper IndoBERT multi-model (fungsi murni, tanpa memuat model)."""

from workers.classify.indobert import _EMO_MAP, _SENT_MAP, _hate_score


def test_hate_score_finds_hate_label() -> None:
    assert _hate_score([{"label": "NON_HATE", "score": 0.9}, {"label": "HATE", "score": 0.1}]) == 0.1
    assert _hate_score([{"label": "HATE", "score": 0.85}]) == 0.85
    assert _hate_score([{"label": "LABEL_1", "score": 0.7}, {"label": "LABEL_0", "score": 0.3}]) == 0.7


def test_hate_score_none_when_no_hate_label() -> None:
    assert _hate_score([{"label": "neutral", "score": 0.9}]) == 0.0


def test_hate_score_accepts_single_dict() -> None:
    assert _hate_score({"label": "hate", "score": 0.5}) == 0.5


def test_emotion_mapping_to_internal_taxonomy() -> None:
    assert _EMO_MAP["happy"] == "joy"
    assert _EMO_MAP["love"] == "trust"
    assert _EMO_MAP["anger"] == "anger"


def test_sentiment_map_covers_label_forms() -> None:
    assert _SENT_MAP["positive"][0] == "pos"
    assert _SENT_MAP["LABEL_2"][0] == "pos"
    assert _SENT_MAP["negative"][0] == "neg"

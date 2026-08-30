"""Uji metrik evaluasi — fungsi murni, tanpa jaringan/model."""

from workers.classify.eval import confusion, prf

LABELS = ["neg", "neu", "pos"]


def test_perfect_prediction() -> None:
    yt = ["neg", "neu", "pos", "pos"]
    m = prf(yt, yt, LABELS)
    assert m["accuracy"] == 1.0
    assert m["macro_f1"] == 1.0


def test_all_wrong() -> None:
    yt = ["neg", "neg"]
    yp = ["pos", "pos"]
    m = prf(yt, yp, LABELS)
    assert m["accuracy"] == 0.0
    assert m["macro_f1"] == 0.0


def test_precision_recall_math() -> None:
    # gold: 2 pos, 1 neg. pred: 2 pos benar, 1 neg salah jadi pos.
    yt = ["pos", "pos", "neg"]
    yp = ["pos", "pos", "pos"]
    m = prf(yt, yp, LABELS)
    pos = m["per_class"]["pos"]
    assert pos["recall"] == 1.0  # 2/2 pos tertangkap
    assert pos["precision"] == round(2 / 3, 3)  # 2 benar dari 3 prediksi pos
    assert m["per_class"]["neg"]["recall"] == 0.0


def test_support_counts() -> None:
    yt = ["neg", "neg", "neu", "pos"]
    m = prf(yt, yt, LABELS)
    assert m["per_class"]["neg"]["support"] == 2
    assert m["per_class"]["pos"]["support"] == 1


def test_confusion_counts_and_other() -> None:
    yt = ["neg", "pos"]
    yp = ["neg", "mixed"]  # 'mixed' bukan label sentimen 3-kelas -> _lain
    cm = confusion(yt, yp, LABELS)
    assert cm["neg"]["neg"] == 1
    assert cm["pos"]["_lain"] == 1

"""Evaluasi classifier terhadap gold set — metrik manual (tanpa sklearn) + loader NusaX.

Gold set: NusaX-Senti (dataset sentimen Indonesia berlabel manusia, IndoNLP), diambil
langsung dari GitHub raw sehingga tak perlu dependensi `datasets`. Di-cache lokal.
Mengukur AKURASI sungguhan (P/R/F1 per kelas + macro-F1) — bukan sekadar kesepakatan
antar-provider. Gate PRD §7.4: F1 makro sentimen >= 0.82.
"""

import csv
import io
from pathlib import Path

import httpx

NUSAX_RAW = "https://raw.githubusercontent.com/IndoNLP/nusax/main/datasets/sentiment"
EMOT_RAW = "https://raw.githubusercontent.com/IndoNLP/indonlu/master/dataset/emot_emotion-twitter"
# label NusaX -> taksonomi internal
_LABEL_MAP = {"negative": "neg", "neutral": "neu", "positive": "pos"}
# label EmoT -> taksonomi emosi internal (EMOTIONS)
_EMOT_MAP = {"anger": "anger", "fear": "fear", "happy": "joy", "love": "trust",
             "sadness": "sadness", "sad": "sadness"}
EMOT_LABELS = ["anger", "fear", "joy", "trust", "sadness"]
# Hate-speech Indonesia (Ibrohim & Budi 2019) — kolom HS biner
HATESPEECH_CSV = (
    "https://raw.githubusercontent.com/okkyibrohim/"
    "id-multi-label-hate-speech-and-abusive-language-detection/master/re_dataset.csv"
)
TOX_LABELS = ["hate", "clean"]


def load_nusax(lang: str = "indonesian", split: str = "test", cache_dir: str = "data/gold") -> list[tuple[str, str]]:
    """Kembalikan [(text, label_internal)]. Cache CSV lokal; ambil dari GitHub bila belum."""
    cache = Path(cache_dir) / f"nusax_{lang}_{split}.csv"
    if cache.exists():
        raw = cache.read_text(encoding="utf-8")
    else:
        resp = httpx.get(f"{NUSAX_RAW}/{lang}/{split}.csv", timeout=60, follow_redirects=True)
        resp.raise_for_status()
        raw = resp.text
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(raw, encoding="utf-8")

    rows: list[tuple[str, str]] = []
    for r in csv.DictReader(io.StringIO(raw)):
        text = (r.get("text") or "").strip()
        label = _LABEL_MAP.get((r.get("label") or "").strip().lower())
        if text and label:
            rows.append((text, label))
    return rows


def load_emot(split: str = "test", cache_dir: str = "data/gold") -> list[tuple[str, str]]:
    """Gold emosi IndoNLU EmoT (tweet Indonesia). Kembalikan [(tweet, emosi_internal)]."""
    cache = Path(cache_dir) / f"emot_{split}.csv"
    if cache.exists():
        raw = cache.read_text(encoding="utf-8")
    else:
        resp = httpx.get(f"{EMOT_RAW}/{split}_preprocess.csv", timeout=60, follow_redirects=True)
        resp.raise_for_status()
        raw = resp.text
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(raw, encoding="utf-8")

    rows: list[tuple[str, str]] = []
    for r in csv.DictReader(io.StringIO(raw)):
        text = (r.get("tweet") or "").strip()
        emo = _EMOT_MAP.get((r.get("label") or "").strip().lower())
        if text and emo:
            rows.append((text, emo))
    return rows


def load_hatespeech(cache_dir: str = "data/gold") -> list[tuple[str, str]]:
    """Gold hate-speech Indonesia (Ibrohim 2019). Kembalikan [(tweet, 'hate'|'clean')].
    File tunggal (tanpa split resmi) berenkoding latin-1."""
    cache = Path(cache_dir) / "hatespeech_id.csv"
    if cache.exists():
        raw = cache.read_bytes()
    else:
        resp = httpx.get(HATESPEECH_CSV, timeout=90, follow_redirects=True)
        resp.raise_for_status()
        raw = resp.content
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(raw)

    rows: list[tuple[str, str]] = []
    for r in csv.DictReader(io.StringIO(raw.decode("latin-1"))):
        text = (r.get("Tweet") or "").strip()
        hs = (r.get("HS") or "").strip()
        if text and hs in ("0", "1"):
            rows.append((text, "hate" if hs == "1" else "clean"))
    return rows


def prf(y_true: list[str], y_pred: list[str], labels: list[str]) -> dict:
    """Precision/Recall/F1 per kelas + macro-F1 + akurasi. Manual, tanpa sklearn."""
    report: dict[str, dict] = {}
    for lab in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == lab and p == lab)
        fp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t != lab and p == lab)
        fn = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == lab and p != lab)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        report[lab] = {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3),
                       "support": sum(1 for t in y_true if t == lab)}
    macro_f1 = round(sum(report[la]["f1"] for la in labels) / len(labels), 3)
    acc = round(sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == p) / len(y_true), 3) if y_true else 0.0
    return {"per_class": report, "macro_f1": macro_f1, "accuracy": acc, "n": len(y_true)}


def confusion(y_true: list[str], y_pred: list[str], labels: list[str]) -> dict:
    """Matriks kebingungan {true: {pred: count}}."""
    m = {t: {p: 0 for p in labels + ["_lain"]} for t in labels}
    for t, p in zip(y_true, y_pred, strict=True):
        if t in m:
            m[t][p if p in labels else "_lain"] += 1
    return m

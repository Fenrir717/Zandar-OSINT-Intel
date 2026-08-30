"""Bake-off classifier terhadap gold set NusaX-Senti (akurasi sungguhan).

    python scripts/eval_classifier.py --provider lexicon
    python scripts/eval_classifier.py --provider indobert
    python scripts/eval_classifier.py --provider lexicon indobert   # bandingkan

Gate PRD §7.4: F1 makro sentimen >= 0.82.
"""

import argparse
import time

from workers.classify.eval import EMOT_LABELS, confusion, load_emot, load_nusax, prf


def make(provider: str):
    if provider == "lexicon":
        from workers.classify.lexicon import LexiconClassifier
        return LexiconClassifier()
    if provider == "indobert":
        from workers.classify.indobert import IndoBertClassifier
        return IndoBertClassifier()
    raise SystemExit(f"provider tak dikenal: {provider}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", nargs="+", default=["lexicon", "indobert"])
    ap.add_argument("--task", choices=["sentiment", "emotion"], default="sentiment")
    ap.add_argument("--split", default="test")
    ap.add_argument("--limit", type=int, default=0, help="0 = semua")
    args = ap.parse_args()

    if args.task == "emotion":
        gold = load_emot(split=args.split)
        labels = EMOT_LABELS
        field = "emotion"
        name = "IndoNLU EmoT (tweet)"
    else:
        gold = load_nusax(split=args.split)
        labels = ["neg", "neu", "pos"]
        field = "sentiment"
        name = "NusaX-Senti Indonesia"

    if args.limit:
        gold = gold[: args.limit]
    texts = [t for t, _ in gold]
    y_true = [lab for _, lab in gold]
    print(f"Gold {name} [{args.split}] — task={args.task}: {len(gold)} kalimat")
    dist = {lab: y_true.count(lab) for lab in labels}
    print(f"Distribusi gold: {dist}\n")

    for prov in args.provider:
        clf = make(prov)
        t = time.time()
        y_pred = [getattr(lab, field) for lab in clf.classify(texts)]
        dur = time.time() - t
        m = prf(y_true, y_pred, labels)
        gate = "LULUS" if m["macro_f1"] >= 0.82 else "belum"
        print(f"=== {prov} ({getattr(clf, 'version', prov)}) — {dur:.1f}s ===")
        print(f"  akurasi={m['accuracy']}  MACRO-F1={m['macro_f1']}  (gate 0.82: {gate})")
        for lab in labels:
            c = m["per_class"][lab]
            print(f"    {lab}: P={c['precision']:.3f} R={c['recall']:.3f} F1={c['f1']:.3f} (n={c['support']})")
        print()


if __name__ == "__main__":
    main()

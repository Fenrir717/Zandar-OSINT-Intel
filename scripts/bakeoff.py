"""Bake-off classifier: Lexicon vs IndoBERT (lokal) vs Flash (LLM) pada gold set
berlabel manusia (PRD §7.4). Metrik akurasi sungguhan (macro-F1) + kecepatan.

Semua provider dievaluasi pada SAMPEL yang SAMA per task (seed tetap) agar adil.
Flash lambat/berbiaya → batasi sampel via --limit. Butuh LLM_PROVIDER nyata utk flash.

    .venv/Scripts/python.exe scripts/bakeoff.py --limit 300
    .venv/Scripts/python.exe scripts/bakeoff.py --providers lexicon indobert --tasks sentiment emotion
"""

import argparse
import random
import time

from workers.classify.eval import (
    EMOT_LABELS,
    TOX_LABELS,
    load_emot,
    load_hatespeech,
    load_nusax,
    prf,
)

TASKS = {
    "sentiment": (lambda: load_nusax(split="test"), ["neg", "neu", "pos"], "sentiment", "NusaX-Senti ID"),
    "emotion": (lambda: load_emot(split="test"), EMOT_LABELS, "emotion", "IndoNLU EmoT"),
    "toxicity": (load_hatespeech, TOX_LABELS, None, "Hate-speech ID (Ibrohim)"),
}


def make(provider: str):
    if provider == "lexicon":
        from workers.classify.lexicon import LexiconClassifier
        return LexiconClassifier()
    if provider == "indobert":
        from workers.classify.indobert import IndoBertClassifier
        return IndoBertClassifier()
    if provider == "flash":
        from workers.classify.flash import FlashClassifier
        return FlashClassifier()
    raise SystemExit(f"provider tak dikenal: {provider}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--providers", nargs="+", default=["lexicon", "indobert", "flash"])
    ap.add_argument("--tasks", nargs="+", default=["sentiment", "emotion", "toxicity"])
    ap.add_argument("--limit", type=int, default=300, help="sampel per task (0=semua)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--tox-threshold", type=float, default=0.5)
    args = ap.parse_args()

    summary: dict[str, dict[str, float]] = {p: {} for p in args.providers}
    clfs = {p: make(p) for p in args.providers}  # instansiasi sekali (muat model sekali)

    for task in args.tasks:
        loader, labels, field, name = TASKS[task]
        gold = loader()
        if args.limit and len(gold) > args.limit:
            gold = random.Random(args.seed).sample(gold, args.limit)
        texts = [t for t, _ in gold]
        y_true = [lab for _, lab in gold]
        dist = {la: y_true.count(la) for la in labels}
        print(f"\n{'=' * 74}\nTASK {task.upper()} — {name} | sampel {len(gold)} | dist {dist}\n{'=' * 74}")

        for prov in args.providers:
            clf = clfs[prov]
            t0 = time.time()
            labs = clf.classify(texts)
            dur = time.time() - t0
            if task == "toxicity":
                y_pred = ["hate" if la.toxicity > args.tox_threshold else "clean" for la in labs]
            else:
                y_pred = [getattr(la, field) for la in labs]
            m = prf(y_true, y_pred, labels)
            summary[prov][task] = m["macro_f1"]
            rate = f"{len(texts) / dur:.0f}/dtk" if dur > 0 else "—"
            print(f"\n  {prov:9} {getattr(clf, 'version', prov):28} acc={m['accuracy']:.3f} "
                  f"MACRO-F1={m['macro_f1']:.3f}  ({dur:.1f}s, {rate})")
            for la in labels:
                c = m["per_class"][la]
                print(f"      {la:12} P={c['precision']:.3f} R={c['recall']:.3f} F1={c['f1']:.3f} (n={c['support']})")

    # Matriks ringkasan
    print(f"\n{'=' * 74}\nRINGKASAN MACRO-F1\n{'=' * 74}")
    header = "  " + "provider".ljust(11) + "".join(t[:9].ljust(11) for t in args.tasks)
    print(header)
    for prov in args.providers:
        row = "  " + prov.ljust(11) + "".join(
            (f"{summary[prov].get(t, 0):.3f}").ljust(11) for t in args.tasks
        )
        print(row)
    print("\nGate PRD §7.4: macro-F1 sentimen >= 0.82. Default produksi = IndoBERT (lokal, privasi).")


if __name__ == "__main__":
    main()

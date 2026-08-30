"""Bandingkan dua provider classifier pada komentar sebuah investigasi.

Preview bake-off (PRD §7.4). TANPA gold set, ini mengukur KESEPAKATAN antar-provider
dan memunculkan kasus tak sepakat (biasanya kasus sulit) — bukan akurasi mutlak.
Akurasi sesungguhnya butuh gold set berlabel manual.

    python scripts/classifier_compare.py --a lexicon --b indobert --limit 300
"""

import argparse
import asyncio

from sqlalchemy import select

from core.db import SessionLocal, engine
from core.models import Comment


async def fetch_texts(limit: int) -> list[tuple[str, str]]:
    async with SessionLocal() as s:
        rows = (await s.execute(select(Comment.content).limit(limit))).all()
        return [r[0] for r in rows]


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


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="lexicon")
    ap.add_argument("--b", default="indobert")
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--show", type=int, default=8, help="jumlah contoh tak sepakat ditampilkan")
    args = ap.parse_args()

    texts = await fetch_texts(args.limit)
    await engine.dispose()
    print(f"{len(texts)} komentar | provider A={args.a} vs B={args.b}")

    clf_a, clf_b = make(args.a), make(args.b)
    print(f"model A={clf_a.version} | model B={clf_b.version}")

    import time
    t = time.time()
    labs_a = clf_a.classify(texts)
    ta = time.time() - t
    t = time.time()
    labs_b = clf_b.classify(texts)
    tb = time.time() - t

    agree = sum(1 for a, b in zip(labs_a, labs_b, strict=True) if a.sentiment == b.sentiment)
    n = len(texts)
    print(f"\nKecepatan: A {ta:.1f}s ({n/ta:.0f}/dtk) | B {tb:.1f}s ({n/tb:.0f}/dtk)")
    print(f"Kesepakatan sentimen: {agree}/{n} = {agree/n:.1%}\n")

    # Matriks kebingungan sederhana
    from collections import Counter
    pairs = Counter((a.sentiment, b.sentiment) for a, b in zip(labs_a, labs_b, strict=True))
    print("Pasangan (A,B) teratas:")
    for (sa, sb), c in pairs.most_common(6):
        mark = "  " if sa == sb else "<>"
        print(f"  {mark} A={sa:5} B={sb:5} : {c}")

    print(f"\nContoh TAK SEPAKAT (maks {args.show}):")
    shown = 0
    for text, a, b in zip(texts, labs_a, labs_b, strict=True):
        if a.sentiment != b.sentiment and shown < args.show:
            print(f"  A={a.sentiment:5} B={b.sentiment:5} | {text[:90]}")
            shown += 1


if __name__ == "__main__":
    asyncio.run(main())

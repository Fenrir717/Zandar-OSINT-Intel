"""Wrapper Neo4j — knowledge graph entitas per-investigasi (Fase 3, PRD §8).

Node :Entity {inv, key, name, type, mentions}; relasi :CO_OCCURS {count} antar entitas
yang muncul di komentar sama. Neo4j = indeks turunan (bisa dibangun ulang dari komentar
+ NER). Driver sinkron — panggil dari task/thread, bukan dari loop async langsung.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

from core.config import get_settings

_driver = None


def driver():
    global _driver
    if _driver is None:
        from neo4j import GraphDatabase

        s = get_settings()
        _driver = GraphDatabase.driver(
            s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password),
            connection_timeout=15.0,              # batas socket connect (hindari gantung saat konek)
            connection_acquisition_timeout=30.0,  # batas tunggu koneksi dari pool
            max_transaction_retry_time=20.0,      # batas retry transaksi terkelola
        )
    return _driver


def _key(typ: str, name: str) -> str:
    from workers.ner.extract import normalize

    return f"{typ}:{normalize(name)}"


def _blank_node(key: str, name: str, typ: str) -> dict:
    """Node dengan akumulator sentimen (Tier 2: sentimen per-target)."""
    return {"key": key, "name": name, "type": typ, "mentions": 0,
            "pos": 0, "neg": 0, "neu": 0, "score_sum": 0.0, "emo": Counter()}


def _merge_agg(dst: dict, src: dict) -> None:
    """Gabung akumulator src ke dst (dipakai saat resolusi entitas)."""
    for f in ("mentions", "pos", "neg", "neu", "score_sum"):
        dst[f] += src.get(f, 0)
    if src.get("emo"):
        dst["emo"].update(src["emo"])


def _resolve(
    nodes: dict[str, dict], pairs: dict[tuple[str, str], int]
) -> tuple[dict[str, dict], dict[tuple[str, str], int]]:
    """Resolusi entitas: (1) satukan nama sama beda-tipe → tipe dominan; (2) untuk
    ORANG, gabung sub-nama ke nama lengkap (token-subset: 'febrie' ⊂ 'febrie adriansyah').
    Akumulator sentimen ikut digabung. Kembalikan node & pasangan yang sudah di-remap."""
    from workers.ner.extract import normalize

    # Pass 1 — kelompokkan per nama ternormalisasi (lintas tipe)
    by_name: dict[str, list[dict]] = {}
    for n in nodes.values():
        by_name.setdefault(normalize(n["name"]), []).append(n)
    canon: dict[str, dict] = {}
    remap: dict[str, str] = {}
    for name, group in by_name.items():
        dom = max(group, key=lambda x: x["mentions"])  # tipe dominan = paling banyak disebut
        ck = f"{dom['type']}:{name}"
        merged = _blank_node(ck, dom["name"], dom["type"])
        for x in group:
            _merge_agg(merged, x)
            remap[x["key"]] = ck
        canon[ck] = merged

    # Pass 2 — ORANG: serap sub-nama ke superset token dgn sebutan terbanyak
    persons = [c for c in canon.values() if c["type"] == "person"]
    ptok = {c["key"]: set(normalize(c["name"]).split()) for c in persons}
    absorbed: dict[str, str] = {}
    for a in persons:
        at = ptok[a["key"]]
        if not at:
            continue
        best = None
        for b in persons:
            if a["key"] != b["key"] and at < ptok[b["key"]] and (best is None or b["mentions"] > best["mentions"]):
                best = b
        if best is not None:
            absorbed[a["key"]] = best["key"]

    def final(k: str) -> str:
        seen: set[str] = set()
        while k in absorbed and k not in seen:
            seen.add(k)
            k = absorbed[k]
        return k

    fnodes: dict[str, dict] = {}
    for ck, node in canon.items():
        fk = final(ck)
        t = fnodes.get(fk)
        if t is None:
            t = _blank_node(fk, canon[fk]["name"], canon[fk]["type"])
            fnodes[fk] = t
        _merge_agg(t, node)
    keymap = {oldk: final(ck) for oldk, ck in remap.items()}

    fpairs: dict[tuple[str, str], int] = {}
    for (a, b), c in pairs.items():
        fa, fb = keymap.get(a, a), keymap.get(b, b)
        if fa == fb:
            continue
        k = (fa, fb) if fa < fb else (fb, fa)
        fpairs[k] = fpairs.get(k, 0) + c
    return fnodes, fpairs


def detect_communities(keys: set[str], pairs: dict[tuple[str, str], int]) -> dict[str, int]:
    """Deteksi komunitas via label-propagation BERBOBOT (tanpa dependensi).

    Tiap node awalnya label unik; iteratif mengadopsi label dgn total bobot tetangga
    terbesar (tie → label terkecil, deterministik). Komunitas dinomori ulang per ukuran
    (0 = terbesar). Node tanpa tetangga → komunitas singleton sendiri.
    """
    adj: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for (a, b), w in pairs.items():
        adj[a].append((b, w))
        adj[b].append((a, w))
    order = sorted(keys)
    label = {k: i for i, k in enumerate(order)}
    for _ in range(30):
        changed = False
        for k in order:
            if not adj[k]:
                continue
            tally: dict[int, int] = defaultdict(int)
            for nb, w in adj[k]:
                tally[label[nb]] += w
            best = min(tally.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            if label[k] != best:
                label[k] = best
                changed = True
        if not changed:
            break
    ranked = {old: new for new, (old, _) in enumerate(Counter(label.values()).most_common())}
    return {k: ranked[v] for k, v in label.items()}


def clear_graph(inv: str) -> None:
    with driver().session() as sess:
        sess.run("MATCH (n:Entity {inv:$inv}) DETACH DELETE n", inv=inv)


def write_graph(inv: str, per_comment: list[list], sentiments: list[dict] | None = None) -> dict:
    """Agregasi entitas + ko-okurensi + SENTIMEN per-target lalu tulis ke Neo4j.

    per_comment: list[list[Entity]] (satu daftar entitas per komentar).
    sentiments : list[dict] sejajar per_comment, tiap item {sentiment, score, emotion}
                 atau None — sentimen komentar itu ditautkan ke entitas yang disebutnya
                 (Tier 2: sentimen per-target-entitas).
    """
    nodes: dict[str, dict] = {}
    pairs: dict[tuple[str, str], int] = {}
    for i, ents in enumerate(per_comment):
        # dedup per komentar berdasar key
        uniq: dict[str, object] = {}
        for e in ents:
            uniq[_key(e.type, e.text)] = e
        sent = sentiments[i] if sentiments and i < len(sentiments) else None
        for k, e in uniq.items():
            n = nodes.get(k)
            if n is None:
                n = _blank_node(k, e.text, e.type)
                nodes[k] = n
            n["mentions"] += 1
            if sent:
                s = sent.get("sentiment")
                n["pos" if s == "pos" else "neg" if s == "neg" else "neu"] += 1
                sc = sent.get("score")
                if isinstance(sc, (int, float)):
                    n["score_sum"] += sc
                if sent.get("emotion"):
                    n["emo"][sent["emotion"]] += 1
        keys = sorted(uniq)
        for a, b in combinations(keys, 2):  # pasangan tak-berurut (a<b) → deterministik
            pairs[(a, b)] = pairs.get((a, b), 0) + 1

    nodes, pairs = _resolve(nodes, pairs)  # resolusi entitas (gabung varian/duplikat)
    comm = detect_communities(set(nodes), pairs)  # deteksi komunitas (CIB)

    rows = []
    for k, n in nodes.items():
        m = n["mentions"] or 1
        rows.append({
            "key": k, "name": n["name"], "type": n["type"], "mentions": n["mentions"],
            "community": comm.get(k, 0),
            "pos": n["pos"], "neg": n["neg"], "neu": n["neu"],
            "sent_score": round(n["score_sum"] / m, 3),
            "emotion": n["emo"].most_common(1)[0][0] if n["emo"] else None,
        })

    clear_graph(inv)
    with driver().session() as sess:
        if rows:
            sess.run(
                "UNWIND $rows AS r MERGE (n:Entity {inv:$inv, key:r.key}) "
                "SET n.name=r.name, n.type=r.type, n.mentions=r.mentions, n.community=r.community, "
                "n.pos=r.pos, n.neg=r.neg, n.neu=r.neu, n.sent_score=r.sent_score, n.emotion=r.emotion",
                inv=inv, rows=rows,
            )
        if pairs:
            edge_rows = [{"a": a, "b": b, "count": c} for (a, b), c in pairs.items()]
            sess.run(
                "UNWIND $rows AS r "
                "MATCH (a:Entity {inv:$inv, key:r.a}), (b:Entity {inv:$inv, key:r.b}) "
                "MERGE (a)-[e:CO_OCCURS]->(b) SET e.count=r.count",
                inv=inv, rows=edge_rows,
            )
    return {"nodes": len(nodes), "edges": len(pairs), "communities": len(set(comm.values()))}


def read_graph(inv: str, node_limit: int = 60, edge_limit: int = 160) -> dict:
    """Kembalikan {nodes:[{id,label,type,mentions,community,pos,neg,neu,sent_score,emotion}],
    edges:[{source,target,weight}]}."""
    with driver().session() as sess:
        nrows = sess.run(
            "MATCH (n:Entity {inv:$inv}) RETURN n.key AS key, n.name AS name, n.type AS type, "
            "n.mentions AS mentions, n.community AS community, n.pos AS pos, n.neg AS neg, "
            "n.neu AS neu, n.sent_score AS sent_score, n.emotion AS emotion "
            "ORDER BY n.mentions DESC LIMIT $lim",
            inv=inv, lim=node_limit,
        ).data()
        keep = {r["key"] for r in nrows}
        erows = sess.run(
            "MATCH (a:Entity {inv:$inv})-[e:CO_OCCURS]->(b:Entity {inv:$inv}) "
            "RETURN a.key AS source, b.key AS target, e.count AS weight ORDER BY e.count DESC LIMIT $lim",
            inv=inv, lim=edge_limit,
        ).data()
    nodes = [{"id": r["key"], "label": r["name"], "type": r["type"], "mentions": r["mentions"],
              "community": r["community"] if r["community"] is not None else 0,
              "pos": r["pos"] or 0, "neg": r["neg"] or 0, "neu": r["neu"] or 0,
              "sent_score": r["sent_score"], "emotion": r["emotion"]} for r in nrows]
    edges = [e for e in erows if e["source"] in keep and e["target"] in keep]
    return {"nodes": nodes, "edges": edges}


def read_entities(inv: str, limit: int = 20) -> list[dict]:
    """Entitas teratas dgn sentimen per-target (untuk panel 'Sentimen per Target')."""
    with driver().session() as sess:
        rows = sess.run(
            "MATCH (n:Entity {inv:$inv}) RETURN n.name AS name, n.type AS type, "
            "n.mentions AS mentions, n.pos AS pos, n.neg AS neg, n.neu AS neu, "
            "n.sent_score AS sent_score, n.emotion AS emotion "
            "ORDER BY n.mentions DESC LIMIT $lim",
            inv=inv, lim=limit,
        ).data()
    return [{"name": r["name"], "type": r["type"], "mentions": r["mentions"],
             "pos": r["pos"] or 0, "neg": r["neg"] or 0, "neu": r["neu"] or 0,
             "sent_score": r["sent_score"], "emotion": r["emotion"]} for r in rows]


def graph_stats(inv: str) -> dict:
    with driver().session() as sess:
        n = sess.run("MATCH (n:Entity {inv:$inv}) RETURN count(n) AS c", inv=inv).single()["c"]
        e = sess.run(
            "MATCH (:Entity {inv:$inv})-[r:CO_OCCURS]->(:Entity {inv:$inv}) RETURN count(r) AS c", inv=inv
        ).single()["c"]
    return {"entities": n, "relations": e}

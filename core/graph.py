"""Wrapper Neo4j — knowledge graph entitas per-investigasi (Fase 3, PRD §8).

Node :Entity {inv, key, name, type, mentions}; relasi :CO_OCCURS {count} antar entitas
yang muncul di komentar sama. Neo4j = indeks turunan (bisa dibangun ulang dari komentar
+ NER). Driver sinkron — panggil dari task/thread, bukan dari loop async langsung.
"""

from __future__ import annotations

from itertools import combinations

from core.config import get_settings

_driver = None


def driver():
    global _driver
    if _driver is None:
        from neo4j import GraphDatabase

        s = get_settings()
        _driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    return _driver


def _key(typ: str, name: str) -> str:
    from workers.ner.extract import normalize

    return f"{typ}:{normalize(name)}"


def clear_graph(inv: str) -> None:
    with driver().session() as sess:
        sess.run("MATCH (n:Entity {inv:$inv}) DETACH DELETE n", inv=inv)


def write_graph(inv: str, per_comment: list[list]) -> dict:
    """Agregasi entitas + ko-okurensi lalu tulis ke Neo4j (idempoten: hapus dulu).

    per_comment: list[list[Entity]] (satu daftar entitas per komentar).
    """
    nodes: dict[str, dict] = {}
    pairs: dict[tuple[str, str], int] = {}
    for ents in per_comment:
        # dedup per komentar berdasar key
        uniq: dict[str, object] = {}
        for e in ents:
            uniq[_key(e.type, e.text)] = e
        for k, e in uniq.items():
            n = nodes.setdefault(k, {"key": k, "name": e.text, "type": e.type, "mentions": 0})
            n["mentions"] += 1
        keys = sorted(uniq)
        for a, b in combinations(keys, 2):  # pasangan tak-berurut (a<b) → deterministik
            pairs[(a, b)] = pairs.get((a, b), 0) + 1

    clear_graph(inv)
    with driver().session() as sess:
        if nodes:
            sess.run(
                "UNWIND $rows AS r MERGE (n:Entity {inv:$inv, key:r.key}) "
                "SET n.name=r.name, n.type=r.type, n.mentions=r.mentions",
                inv=inv, rows=list(nodes.values()),
            )
        if pairs:
            edge_rows = [{"a": a, "b": b, "count": c} for (a, b), c in pairs.items()]
            sess.run(
                "UNWIND $rows AS r "
                "MATCH (a:Entity {inv:$inv, key:r.a}), (b:Entity {inv:$inv, key:r.b}) "
                "MERGE (a)-[e:CO_OCCURS]->(b) SET e.count=r.count",
                inv=inv, rows=edge_rows,
            )
    return {"nodes": len(nodes), "edges": len(pairs)}


def read_graph(inv: str, node_limit: int = 60, edge_limit: int = 160) -> dict:
    """Kembalikan {nodes:[{id,label,type,mentions}], edges:[{source,target,weight}]}."""
    with driver().session() as sess:
        nrows = sess.run(
            "MATCH (n:Entity {inv:$inv}) RETURN n.key AS key, n.name AS name, n.type AS type, "
            "n.mentions AS mentions ORDER BY n.mentions DESC LIMIT $lim",
            inv=inv, lim=node_limit,
        ).data()
        keep = {r["key"] for r in nrows}
        erows = sess.run(
            "MATCH (a:Entity {inv:$inv})-[e:CO_OCCURS]->(b:Entity {inv:$inv}) "
            "RETURN a.key AS source, b.key AS target, e.count AS weight ORDER BY e.count DESC LIMIT $lim",
            inv=inv, lim=edge_limit,
        ).data()
    nodes = [{"id": r["key"], "label": r["name"], "type": r["type"], "mentions": r["mentions"]} for r in nrows]
    edges = [e for e in erows if e["source"] in keep and e["target"] in keep]
    return {"nodes": nodes, "edges": edges}


def graph_stats(inv: str) -> dict:
    with driver().session() as sess:
        n = sess.run("MATCH (n:Entity {inv:$inv}) RETURN count(n) AS c", inv=inv).single()["c"]
        e = sess.run(
            "MATCH (:Entity {inv:$inv})-[r:CO_OCCURS]->(:Entity {inv:$inv}) RETURN count(r) AS c", inv=inv
        ).single()["c"]
    return {"entities": n, "relations": e}

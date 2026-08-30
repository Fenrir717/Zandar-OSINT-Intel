"""Wrapper Qdrant — koleksi vektor komentar untuk pencarian semantik (PRD §8.3).

Koleksi dibuat dengan dimensi embedder aktif (cosine). Payload menyimpan filter
(investigation_id, platform, lang, published_at) agar pencarian bisa di-scope.
"""

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from core.config import get_settings


def client() -> QdrantClient:
    return QdrantClient(url=get_settings().qdrant_url, timeout=30)


def ensure_collection(dim: int, name: str | None = None) -> str:
    name = name or get_settings().qdrant_collection
    c = client()
    existing = {col.name for col in c.get_collections().collections}
    if name in existing:
        # Bila dimensi berubah (ganti embedder), buat ulang — indeks lama tak kompatibel
        cur = c.get_collection(name).config.params.vectors.size
        if cur != dim:
            c.delete_collection(name)
            existing.discard(name)
    if name not in existing:
        c.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )
        # index payload untuk filter cepat
        for field, schema in [("investigation_id", "keyword"), ("platform", "keyword"), ("lang", "keyword")]:
            try:
                c.create_payload_index(name, field_name=field, field_schema=schema)
            except Exception:
                pass
    return name


def _point_id(comment_id: str) -> str:
    # Qdrant point id boleh UUID; pakai comment_id (UUID) langsung → idempoten
    return comment_id


def upsert(vectors: list[list[float]], payloads: list[dict], name: str | None = None) -> int:
    name = name or get_settings().qdrant_collection
    points = [
        qm.PointStruct(id=_point_id(p["comment_id"]), vector=v, payload=p)
        for v, p in zip(vectors, payloads, strict=True)
    ]
    client().upsert(collection_name=name, points=points)
    return len(points)


def search(
    vector: list[float], investigation_id: str, limit: int = 50,
    platform: str | None = None, lang: str | None = None, name: str | None = None,
) -> list[dict]:
    """Pencarian semantik, WAJIB di-scope ke satu investigasi (PRD §8.3)."""
    name = name or get_settings().qdrant_collection
    must: list = [qm.FieldCondition(key="investigation_id", match=qm.MatchValue(value=investigation_id))]
    if platform:
        must.append(qm.FieldCondition(key="platform", match=qm.MatchValue(value=platform)))
    if lang:
        must.append(qm.FieldCondition(key="lang", match=qm.MatchValue(value=lang)))
    hits = client().query_points(
        collection_name=name, query=vector, limit=limit,
        query_filter=qm.Filter(must=must), with_payload=True,
    ).points
    return [{"score": h.score, **(h.payload or {})} for h in hits]


def count(name: str | None = None) -> int:
    name = name or get_settings().qdrant_collection
    try:
        return client().count(collection_name=name).count
    except Exception:
        return 0

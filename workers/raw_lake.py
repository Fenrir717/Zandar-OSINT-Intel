"""Raw data lake (MinIO/S3) — PRD KRITIK-6: simpan payload mentah SEBELUM tahap
apa pun, immutable, agar model yang membaik bisa diterapkan retroaktif via replay.
Kunci objek: raw/{platform}/{collection_run_id}/{external_id}.json
"""

import io
import json
import re

from minio import Minio

from core.config import get_settings

_KEY_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def _client() -> Minio:
    s = get_settings()
    return Minio(
        s.minio_endpoint,
        access_key=s.minio_access_key,
        secret_key=s.minio_secret_key,
        secure=False,  # dev; produksi: TLS
    )


def ensure_bucket() -> None:
    client = _client()
    bucket = get_settings().minio_bucket_raw
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def put_raw(platform: str, run_id: str, external_id: str, payload: dict) -> str:
    """Simpan payload mentah; kembalikan referensi objek untuk kolom comments.raw_ref."""
    bucket = get_settings().minio_bucket_raw
    safe_id = _KEY_SAFE.sub("_", external_id)[:200]
    key = f"raw/{platform}/{run_id}/{safe_id}.json"
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    _client().put_object(bucket, key, io.BytesIO(body), len(body), content_type="application/json")
    return f"s3://{bucket}/{key}"


def put_report(investigation_id: str, report_id: str, payload: dict) -> str:
    """Simpan dokumen laporan (Graph D); kembalikan ref untuk kolom reports.content_ref."""
    bucket = get_settings().minio_bucket_raw
    key = f"reports/{investigation_id}/{report_id}.json"
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    _client().put_object(bucket, key, io.BytesIO(body), len(body), content_type="application/json")
    return f"s3://{bucket}/{key}"


def get_json(ref: str) -> dict:
    """Baca objek JSON dari ref 's3://bucket/key' (mis. reports.content_ref)."""
    if not ref or not ref.startswith("s3://"):
        raise ValueError(f"ref objek tidak valid: {ref!r}")
    bucket, _, key = ref[len("s3://"):].partition("/")
    resp = _client().get_object(bucket, key)
    try:
        return json.loads(resp.read().decode("utf-8"))
    finally:
        resp.close()
        resp.release_conn()

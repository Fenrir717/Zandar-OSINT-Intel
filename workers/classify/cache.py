"""Cache hasil klasifikasi di Redis (Tier 1 efisiensi).

Teks identik (spam, template, retweet) tidak perlu dianalisis ulang oleh IndoBERT
+ refine. Kunci = hash SHA-256 dari (versi_pipeline : versi_model : teks-terproses),
sehingga perubahan model/pipeline OTOMATIS menganggap cache lama kedaluwarsa.
Nilai = Label ter-JSON, TTL 48 jam. Gagal Redis → transparan (tanpa cache).
"""

import hashlib
import json

from core.config import get_settings
from workers.classify.base import Label

_TTL = 48 * 3600          # 48 jam
_PREFIX = "zandar:clf:"
_PIPE_VERSION = "t1"      # bump bila preprocess/refine/skema Label berubah
_FIELDS = (
    "sentiment", "sentiment_score", "emotion", "intent", "toxicity",
    "model_version", "confidence", "is_sarcasm",
)

_client = None


def _redis():
    global _client
    if _client is None:
        import redis

        _client = redis.from_url(get_settings().redis_url, decode_responses=True)
    return _client


def _key(text: str, version: str) -> str:
    raw = f"{_PIPE_VERSION}:{version}:{text}".encode()
    return _PREFIX + hashlib.sha256(raw).hexdigest()


def get_cached(texts: list[str], version: str) -> list[Label | None]:
    """Ambil Label ter-cache untuk tiap teks (None bila miss). Aman bila Redis mati."""
    try:
        vals = _redis().mget([_key(t, version) for t in texts])
    except Exception:  # noqa: BLE001 — Redis mati/format → anggap semua miss
        return [None] * len(texts)
    out: list[Label | None] = []
    for v in vals:
        if not v:
            out.append(None)
            continue
        try:
            d = json.loads(v)
            out.append(Label(**{k: d[k] for k in _FIELDS if k in d}))
        except Exception:  # noqa: BLE001 — entri rusak/lawas → miss
            out.append(None)
    return out


def set_cached(texts: list[str], labels: list[Label], version: str) -> None:
    """Simpan Label per teks (TTL). Aman bila Redis mati."""
    try:
        pipe = _redis().pipeline()
        for t, lab in zip(texts, labels, strict=True):
            payload = json.dumps({k: getattr(lab, k) for k in _FIELDS})
            pipe.set(_key(t, version), payload, ex=_TTL)
        pipe.execute()
    except Exception:  # noqa: BLE001 — cache best-effort
        pass

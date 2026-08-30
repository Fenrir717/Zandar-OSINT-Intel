"""Adapter HAR-import — parse file .har yang diekspor analis dari browser.

Alur SAH & human-in-the-loop: analis membuka X/Threads MANUAL sebagai manusia
(aktivitas asli, bukan bot), scroll, lalu ekspor tab Network sebagai .har. Adapter
ini hanya MEM-PARSE file itu — tidak ada jaringan, akun tumbal, atau otomasi massal.
Cocok terutama untuk Threads (tanpa API) dan X skala kecil.

Ekstraksi bersifat heuristik: menelusuri body respons JSON (GraphQL) dan mengumpulkan
objek yang punya field teks + id. Bisa dipersempit dengan field_map di query.

query = {
    "har_path": "C:/.../threads.har",
    "platform": "threads",              # label data (x|threads|...)
    "text_fields": ["text","full_text","caption"],   # opsional
    "id_fields": ["id","pk","rest_id","code"],        # opsional
    "keywords": ["stimulus"],           # opsional filter
    "max_items": 500,
}
"""

import json
from collections.abc import Iterator
from datetime import UTC, datetime

from workers.adapters.base import AdapterNotConfigured, BaseAdapter, RawItem

_DEFAULT_TEXT = ("full_text", "text", "caption", "content", "body")
_DEFAULT_ID = ("id", "pk", "rest_id", "code", "id_str")
_AUTHOR_HINTS = ("screen_name", "username", "unique_id", "handle", "name")
_TIME_HINTS = ("created_at", "taken_at", "publish_date", "timestamp", "time")


class HarImportAdapter(BaseAdapter):
    platform = "har"  # override per item dari config["platform"]
    key = "har"
    tier = "free"
    requires_credentials = False
    rate_note = "Tanpa jaringan — hanya parse file .har lokal. Skala kecil, human-in-the-loop."
    legal_note = (
        "Analis mengambil data manual sebagai manusia lalu mengekspor .har; adapter hanya "
        "mem-parse. Tanpa akun tumbal/otomasi massal. Hormati ToS platform sumber."
    )

    def collect(self, query: dict) -> Iterator[RawItem]:
        har_path = query.get("har_path") or self.config.get("har_path")
        if not har_path:
            raise AdapterNotConfigured("HAR-import butuh 'har_path' pada query/config")

        platform = query.get("platform") or self.config.get("platform", "har")
        text_fields = tuple(query.get("text_fields", _DEFAULT_TEXT))
        id_fields = tuple(query.get("id_fields", _DEFAULT_ID))
        keywords = [k.lower() for k in query.get("keywords", [])]
        max_items = int(query.get("max_items", 500))

        try:
            with open(har_path, encoding="utf-8") as f:
                har = json.load(f)
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"Gagal membaca HAR: {exc}") from exc

        seen: set[str] = set()
        emitted = 0
        for entry in har.get("log", {}).get("entries", []):
            body = _entry_json(entry)
            if body is None:
                continue
            for obj in _walk_posts(body, text_fields, id_fields):
                if emitted >= max_items:
                    return
                ext_id = str(_first(obj, id_fields))
                text = str(_first(obj, text_fields) or "").strip()
                if not text or ext_id in seen:
                    continue
                if keywords and not any(k in text.lower() for k in keywords):
                    continue
                seen.add(ext_id)
                yield RawItem(
                    platform=platform,
                    external_id=f"{platform}:{ext_id}"[:255],
                    author=str(_first(obj, _AUTHOR_HINTS) or "unknown"),
                    content=text,
                    published_at=_coerce_ts(_first(obj, _TIME_HINTS)),
                    raw=obj,
                )
                emitted += 1


def _entry_json(entry: dict) -> object | None:
    resp = entry.get("response", {})
    content = resp.get("content", {})
    mime = content.get("mimeType", "")
    text = content.get("text")
    if not text or "json" not in mime:
        return None
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _walk_posts(node: object, text_fields: tuple, id_fields: tuple) -> Iterator[dict]:
    """Telusuri JSON secara rekursif; yield dict yang punya field teks DAN id."""
    if isinstance(node, dict):
        has_text = any(k in node and isinstance(node[k], str) and node[k].strip() for k in text_fields)
        has_id = any(k in node for k in id_fields)
        if has_text and has_id:
            yield node
        for v in node.values():
            yield from _walk_posts(v, text_fields, id_fields)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_posts(v, text_fields, id_fields)


def _first(obj: dict, keys: tuple):
    for k in keys:
        if k in obj and obj[k] not in (None, ""):
            return obj[k]
    return None


def _coerce_ts(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = value / 1000 if value > 1e12 else value  # ms → s
        try:
            return datetime.fromtimestamp(v, tz=UTC)
        except (ValueError, OSError):
            return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

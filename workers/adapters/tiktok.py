"""Adapter TikTok — HANYA lewat penyedia data pihak ketiga berkontrak.

Kenapa tidak langsung ke TikTok: Research API resmi TikTok terbatas untuk
institusi akademik di US/EEA/UK/CH (pengguna komersial eksplisit tidak
eligible), dan tidak ada akses komersial gratis ke data publiknya. Scraping
langsung melanggar ToS TikTok dan berarti perang tanpa akhir melawan anti-bot.

Jalur yang tersisa: vendor data (mis. penyedia snapshot/scraping berkontrak).
Karena setiap vendor punya skema respons berbeda, adapter ini TIDAK menebak
skema siapa pun — ia meminta PEMETAAN FIELD eksplisit di config sumber, yang
diisi setelah kamu melihat satu respons nyata dari vendor pilihanmu.

Sources.config = {
    "base_url": "https://api.vendor.example/tiktok/comments",
    "api_key": "...",
    "auth_header": "X-API-Key",          # opsional, default Authorization: Bearer
    "items_path": "data.comments",       # jalur ke array item di respons
    "field_map": {
        "external_id": "cid",
        "author": "user.unique_id",
        "content": "text",
        "url": "share_url",
        "published_at": "create_time"
    }
}
query diteruskan apa adanya sebagai query-string ke vendor.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import httpx

from workers.adapters.base import AdapterNotConfigured, BaseAdapter, RawItem


class TikTokAdapter(BaseAdapter):
    platform = "tiktok"
    tier = "vendor"
    requires_credentials = True
    required_config = ("base_url", "api_key", "items_path", "field_map")
    rate_note = "Mengikuti kuota kontrak vendor."
    cost_note = "Berbayar sesuai kontrak vendor (per-call atau snapshot)."
    legal_note = (
        "Tidak ada akses komersial resmi ke data publik TikTok. Wajib memakai vendor yang "
        "patuh GDPR/UU PDP dan hanya mengumpulkan data publik. Jangan scraping langsung."
    )

    def collect(self, query: dict) -> Iterator[RawItem]:
        self.require_config(*self.required_config)

        base_url = self.config["base_url"]
        field_map = self.config["field_map"]
        for required in ("external_id", "author", "content"):
            if required not in field_map:
                raise AdapterNotConfigured(f"field_map wajib memetakan '{required}'")

        auth_header = self.config.get("auth_header", "Authorization")
        api_key = self.config["api_key"]
        headers = {
            auth_header: api_key if auth_header != "Authorization" else f"Bearer {api_key}",
            "User-Agent": "ZandarOSINT/0.1",
        }

        try:
            resp = httpx.get(base_url, params=query, headers=headers, timeout=60)
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError(f"Vendor TikTok gagal merespons: {exc}") from exc

        for item in _dig(payload, self.config["items_path"]) or []:
            external_id = _dig(item, field_map["external_id"])
            content = _dig(item, field_map["content"])
            if not external_id or not content:
                continue
            yield RawItem(
                platform=self.platform,
                external_id=str(external_id)[:255],
                author=str(_dig(item, field_map["author"]) or "unknown"),
                content=str(content),
                url=_dig(item, field_map.get("url", "")) if field_map.get("url") else None,
                published_at=_coerce_ts(_dig(item, field_map.get("published_at", ""))),
                raw=item,
            )


def _dig(data, path: str):
    """Ambil nilai bersarang lewat jalur bertitik ('user.unique_id')."""
    if not path:
        return None
    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _coerce_ts(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):  # epoch detik
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (ValueError, OSError):
            return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

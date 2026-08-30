"""Base adapter untuk sumber via PENYEDIA DATA pihak ketiga (shadow API).

Dipakai platform tanpa akses resmi murah (TikTok, X). Vendor menanggung
scraping/ToS; kita konsumsi API bersih dengan PEMETAAN FIELD eksplisit — tidak
menebak skema vendor mana pun. Isi config setelah melihat satu respons nyata.

Sources.config = {
    "base_url": "https://api.vendor.example/...",
    "api_key": "...",
    "auth_header": "Authorization",        # default; nilai jadi "Bearer <key>"
    "items_path": "data.items",            # jalur ke array item di respons
    "field_map": {"external_id": "id", "author": "user.name", "content": "text",
                  "url": "share_url", "published_at": "created_at"}
}
query diteruskan apa adanya sebagai query-string ke vendor.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import httpx

from workers.adapters.base import AdapterNotConfigured, BaseAdapter, RawItem


class VendorAdapter(BaseAdapter):
    tier = "vendor"
    requires_credentials = True
    required_config = ("base_url", "api_key", "items_path", "field_map")

    def collect(self, query: dict) -> Iterator[RawItem]:
        self.require_config(*self.required_config)
        field_map = self.config["field_map"]
        for req in ("external_id", "author", "content"):
            if req not in field_map:
                raise AdapterNotConfigured(f"field_map wajib memetakan '{req}'")

        auth_header = self.config.get("auth_header", "Authorization")
        api_key = self.config["api_key"]
        headers = {
            auth_header: f"Bearer {api_key}" if auth_header == "Authorization" else api_key,
            "User-Agent": "ZandarOSINT/0.1",
        }
        try:
            resp = httpx.get(self.config["base_url"], params=query, headers=headers, timeout=60)
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError(f"Vendor {self.platform} gagal merespons: {exc}") from exc

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
                url=_dig(item, field_map["url"]) if field_map.get("url") else None,
                published_at=_coerce_ts(_dig(item, field_map.get("published_at", ""))),
                raw=item,
            )


def _dig(data, path: str):
    """Ambil nilai bersarang lewat jalur bertitik ('user.name')."""
    if not path:
        return None
    cur = data
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _coerce_ts(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (ValueError, OSError):
            return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

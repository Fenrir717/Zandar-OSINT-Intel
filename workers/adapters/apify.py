"""Adapter Apify — sumber via actor Apify (penyedia scraping berkontrak, bayar-per-run).

Untuk sumber ANTI-BOT (Google Maps reviews, Shopee, Tokopedia, Instagram, TikTok, dst.)
yang tak etis / tak maintainable bila di-scrape sendiri (lihat prinsip kepatuhan: TANPA
scraping gerilya / evasion). Apify menanggung akses + ToS + anti-bot; kita cukup jadi
klien API dataset-nya, dengan PEMETAAN FIELD eksplisit — TAK menebak skema actor.
Isi `field_map` setelah melihat satu run nyata.

Alur: POST run-sync-get-dataset-items (blok sampai actor selesai) → array item dataset
→ field_map → RawItem. Satu adapter melayani BANYAK actor (ganti `actor_id` di config).

Sources.config = {
    "api_token": "apify_api_...",          # via admin/Sources — TAK PERNAH di kode
    "actor_id": "compass~crawler-google-places",  # id actor ('user~nama')
    "input": {"language": "id", "maxReviews": 100},  # input dasar actor
    "items_path": "",                      # "" = array top-level dataset; atau "results"
    "field_map": {                         # jalur bertitik ke field item dataset
        "external_id": "reviewId", "author": "name", "content": "text",
        "url": "reviewUrl", "published_at": "publishedAtDate", "rating": "stars",
        "title": "title"                   # opsional
    },
    "max_items": 500,                      # cap item dataset (kendali biaya)
    "timeout_s": 180                       # batas tunggu run sinkron
}
query digabung ke input actor (mis. {"searchStringsArray": [...]} atau {"startUrls": [...]}).

Catatan biaya JUJUR: `max_items` membatasi item yang DIAMBIL, tapi actor bisa tetap
menagih per-run/compute; batasi juga lewat input actor (mis. maxReviews) di config.
"""

from collections.abc import Iterator

import httpx

from workers.adapters.base import AdapterNotConfigured, BaseAdapter, RawItem
from workers.adapters.vendor_base import _coerce_ts, _dig

_API = "https://api.apify.com/v2"


def _as_star(value: object) -> int | None:
    """Normalisasi rating apa pun (float/int/str) ke bintang bulat 1-5, else None."""
    if value is None:
        return None
    try:
        n = round(float(value))
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= 5 else None


class ApifyAdapter(BaseAdapter):
    platform = "apify"
    key = "apify"
    tier = "vendor"
    requires_credentials = True
    required_config = ("api_token", "actor_id", "field_map")
    rate_note = "Bayar-per-run (Apify); cap max_items + limit input actor untuk kendali biaya."
    legal_note = "Penyedia berkontrak menanggung akses & ToS; kita konsumsi dataset actor."

    def collect(self, query: dict) -> Iterator[RawItem]:
        self.require_config(*self.required_config)
        field_map = self.config["field_map"]
        for req in ("external_id", "content"):
            if req not in field_map:
                raise AdapterNotConfigured(f"field_map wajib memetakan '{req}'")

        token = self.config["api_token"]
        actor = self.config["actor_id"]
        max_items = max(1, int(self.config.get("max_items", 1000)))
        timeout_s = max(30, int(self.config.get("timeout_s", 180)))

        # Input dasar actor digabung dengan query koleksi (query menimpa input dasar).
        actor_input = dict(self.config.get("input") or {})
        if query:
            actor_input.update(query)

        endpoint = f"{_API}/acts/{actor}/run-sync-get-dataset-items"
        try:
            resp = httpx.post(
                endpoint,
                params={"token": token, "maxItems": max_items},
                json=actor_input,
                headers={"User-Agent": "ZandarOSINT/0.1"},
                timeout=timeout_s + 30,
            )
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError(f"Apify actor {actor} gagal merespons: {exc}") from exc

        items_path = self.config.get("items_path")
        rows = _dig(payload, items_path) if items_path else payload
        if not isinstance(rows, list):
            return

        for item in rows:
            if not isinstance(item, dict):
                continue
            external_id = _dig(item, field_map["external_id"])
            content = _dig(item, field_map["content"])
            if not external_id or not content:
                continue

            raw = dict(item)
            if field_map.get("rating"):
                star = _as_star(_dig(item, field_map["rating"]))
                if star is not None:
                    raw["score"] = star  # agar _review_rating menangkap → kolom rating

            title = _dig(item, field_map["title"]) if field_map.get("title") else None
            yield RawItem(
                platform=self.platform,
                external_id=str(external_id)[:255],
                author=str(_dig(item, field_map["author"]) or "unknown") if field_map.get("author") else "unknown",
                content=str(content),
                url=_dig(item, field_map["url"]) if field_map.get("url") else None,
                published_at=_coerce_ts(_dig(item, field_map.get("published_at", ""))),
                title=str(title) if title else None,
                raw=raw,
            )

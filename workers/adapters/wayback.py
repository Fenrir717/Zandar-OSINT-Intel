"""Adapter Wayback Machine — konten historis dari arsip publik Archive.org.

Menemukan snapshot lewat CDX API (gratis, tanpa key), lalu mengekstrak teks artikel
tiap snapshot via trafilatura. Berguna untuk: artikel yang sudah dihapus/diubah,
melihat evolusi narasi lintas waktu, dan sumber yang memblokir akses langsung.

query = {
    "url": "cnnindonesia.com/nasional*",   # pola URL (CDX matchType)
    "from": "20260101", "to": "20261231",  # opsional (YYYYMMDD)
    "limit": 50,
    "keywords": ["stimulus"],
}
"""

from collections.abc import Iterator
from datetime import datetime

import httpx

from workers.adapters.base import AdapterNotConfigured, BaseAdapter, RawItem
from workers.adapters.web_extract import USER_AGENT, fetch_and_extract

CDX = "http://web.archive.org/cdx/search/cdx"


class WaybackAdapter(BaseAdapter):
    platform = "wayback"
    key = "wayback"
    tier = "free"
    requires_credentials = False
    rate_note = "CDX API gratis tanpa key; jeda per snapshot saat ekstraksi."
    legal_note = "Arsip publik Archive.org; konten yang sudah dipublikasikan."

    def collect(self, query: dict) -> Iterator[RawItem]:
        url = query.get("url")
        if not url:
            raise AdapterNotConfigured("Wayback butuh 'url' (pola CDX) pada query")

        keywords = [k.lower() for k in query.get("keywords", [])]
        limit = int(query.get("limit", 50))
        params = {
            "url": url,
            "output": "json",
            "fl": "timestamp,original,statuscode,mimetype",
            "filter": "statuscode:200",
            "collapse": "digest",
            "limit": limit,
        }
        if url.endswith("*") or "*" in url:
            params["matchType"] = "prefix"
        if query.get("from"):
            params["from"] = query["from"]
        if query.get("to"):
            params["to"] = query["to"]

        try:
            resp = httpx.get(CDX, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
            resp.raise_for_status()
            rows = resp.json()
        except (httpx.HTTPError, ValueError):
            return
        if not rows or len(rows) < 2:
            return

        for row in rows[1:]:  # baris 0 = header
            timestamp, original = row[0], row[1]
            snapshot = f"http://web.archive.org/web/{timestamp}/{original}"
            extracted = fetch_and_extract(snapshot, respect_robots=False)  # arsip, bukan situs asli
            if extracted is None:
                continue
            text = extracted["text"]
            if keywords and not any(k in text.lower() for k in keywords):
                continue
            title = extracted["title"] or original
            yield RawItem(
                platform=self.platform,
                external_id=f"wb:{timestamp}:{original}"[:255],
                author=_domain(original),
                content=f"{title}\n\n{text}",
                url=snapshot,
                published_at=_parse_ts(timestamp),
                title=title,
                raw={"timestamp": timestamp, "original": original, "snapshot": snapshot},
            )


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y%m%d%H%M%S")
    except ValueError:
        return None


def _domain(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url if "//" in url else "http://" + url).netloc or "unknown"

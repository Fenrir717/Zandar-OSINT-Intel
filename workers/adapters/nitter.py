"""Adapter Nitter — front-end publik alternatif X via RSS.

PERINGATAN REALITAS 2026: mayoritas instance Nitter SUDAH MATI (X memutus akses
guest sejak 2024). Adapter ini disediakan untuk kelengkapan; WAJIB memberi
`base_url` instance yang masih hidup — tidak ada default karena tak ada yang andal.
Untuk X yang berkelanjutan, pakai adapter x (resmi) atau x_vendor.

query = {
    "base_url": "https://nitter.example.net",   # instance hidup pilihan analis
    "search": "stimulus pangan",                # -> /search/rss?q=...
    "profiles": ["akun"],                       # -> /akun/rss
    "keywords": ["stimulus"],
}
"""

import time
from calendar import timegm
from collections.abc import Iterator
from datetime import UTC, datetime

import feedparser
import httpx

from workers.adapters.base import AdapterNotConfigured, BaseAdapter, RawItem
from workers.adapters.web_extract import USER_AGENT


class NitterAdapter(BaseAdapter):
    platform = "x"
    key = "nitter"
    tier = "free"
    requires_credentials = False
    rate_note = "Bergantung instance Nitter pihak ketiga; mayoritas mati sejak 2024 — tidak andal."
    legal_note = "Front-end publik X. Instance yang dipilih analis; hormati ketentuannya."

    def collect(self, query: dict) -> Iterator[RawItem]:
        base = (query.get("base_url") or self.config.get("base_url") or "").rstrip("/")
        if not base:
            raise AdapterNotConfigured(
                "Nitter butuh 'base_url' instance hidup — tak ada default (instance publik mayoritas mati). "
                "Pertimbangkan adapter x_vendor untuk X yang berkelanjutan."
            )

        keywords = [k.lower() for k in query.get("keywords", [])]
        feeds: list[str] = []
        if query.get("search"):
            from urllib.parse import quote
            feeds.append(f"{base}/search/rss?f=tweets&q={quote(query['search'])}")
        for prof in query.get("profiles", []):
            feeds.append(f"{base}/{prof}/rss")

        for feed_url in feeds:
            try:
                resp = httpx.get(feed_url, headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True)
                resp.raise_for_status()
            except httpx.HTTPError:
                continue
            for entry in feedparser.parse(resp.content).entries:
                text = (entry.get("title", "") + " " + entry.get("summary", "")).strip()
                ext_id = entry.get("id") or entry.get("link")
                if not text or not ext_id:
                    continue
                if keywords and not any(k in text.lower() for k in keywords):
                    continue
                struct = entry.get("published_parsed")
                published = datetime.fromtimestamp(timegm(struct), tz=UTC) if struct else None
                yield RawItem(
                    platform=self.platform,
                    external_id=str(ext_id)[:255],
                    author=entry.get("author", "unknown"),
                    content=text,
                    url=entry.get("link"),
                    published_at=published,
                    raw={k: v for k, v in dict(entry).items() if isinstance(v, (str, int, float))},
                )
            time.sleep(1)

"""Adapter RSS/Atom — sumber prioritas v1 (gratis, legal, stabil).

query = {
    "feeds": ["https://.../rss", ...],
    "keywords": ["stimulus", ...],   # opsional; kosong = ambil semua
}
"""

import time
from calendar import timegm
from collections.abc import Iterator
from datetime import UTC, datetime

import feedparser
import httpx

from workers.adapters.base import BaseAdapter, RawItem

USER_AGENT = "ZandarOSINT/0.1 (research; contact via repo)"


class RssAdapter(BaseAdapter):
    platform = "rss"
    tier = "free"
    requires_credentials = False
    rate_note = "Jeda 1 detik antar feed; tanpa batas resmi."
    legal_note = "Feed dipublikasikan untuk konsumsi mesin."

    def collect(self, query: dict) -> Iterator[RawItem]:
        feeds: list[str] = query.get("feeds", [])
        keywords = [k.lower() for k in query.get("keywords", [])]

        for feed_url in feeds:
            try:
                resp = httpx.get(
                    feed_url,
                    headers={"User-Agent": USER_AGENT},
                    timeout=30,
                    follow_redirects=True,
                )
                resp.raise_for_status()
            except httpx.HTTPError:
                continue  # feed mati tidak boleh menggagalkan feed lain

            parsed = feedparser.parse(resp.content)
            for entry in parsed.entries:
                title = entry.get("title", "") or ""
                summary = entry.get("summary", "") or ""
                text = f"{title}. {summary}".strip(". ")
                if keywords and not any(k in text.lower() for k in keywords):
                    continue

                external_id = entry.get("id") or entry.get("link") or title
                if not external_id or not text:
                    continue

                published = None
                struct = entry.get("published_parsed") or entry.get("updated_parsed")
                if struct is not None:
                    published = datetime.fromtimestamp(timegm(struct), tz=UTC)

                yield RawItem(
                    platform=self.platform,
                    external_id=str(external_id)[:255],
                    author=entry.get("author") or parsed.feed.get("title", feed_url),
                    content=text,
                    url=entry.get("link"),
                    published_at=published,
                    raw={k: v for k, v in dict(entry).items() if isinstance(v, (str, int, float, bool, list, dict))},
                )
            time.sleep(1)  # sopan antar feed

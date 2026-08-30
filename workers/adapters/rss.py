"""Adapter RSS/Atom — sumber prioritas v1 (gratis, legal, stabil).

query = {
    "feeds": ["https://.../rss", ...],   # opsional
    "keywords": ["laundry", ...],        # opsional; filter isi
}

Bila `feeds` KOSONG tapi `keywords` diberi, adapter otomatis menurunkan feed
**Google News RSS** yang dapat dicari per-keyword (gratis, tanpa API key) — sehingga
Scan Commander yang hanya memberi keyword tetap menghasilkan wacana nyata.
"""

import time
import urllib.parse
from calendar import timegm
from collections.abc import Iterator
from datetime import UTC, datetime

import feedparser
import httpx

from workers.adapters.base import BaseAdapter, RawItem

# UA gaya-browser: sebagian server feed (mis. Google News) menolak UA non-browser.
USER_AGENT = "Mozilla/5.0 (compatible; ZandarOSINT/0.1; +research)"


def google_news_feeds(keywords: list[str], lang: str = "id", country: str = "ID",
                      max_terms: int = 6) -> list[str]:
    """Bangun URL Google News RSS pencarian dari keyword (OR gabungan). Satu feed =
    union hasil; Google News mengembalikan hingga ~100 artikel terbaru."""
    terms = [k for k in keywords if k][:max_terms]
    if not terms:
        return []
    q = " OR ".join(f'"{t}"' if " " in t else t for t in terms)
    url = (f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}"
           f"&hl={lang}&gl={country}&ceid={country}:{lang}")
    return [url]


class RssAdapter(BaseAdapter):
    platform = "rss"
    tier = "free"
    requires_credentials = False
    rate_note = "Jeda 1 detik antar feed; tanpa batas resmi."
    legal_note = "Feed dipublikasikan untuk konsumsi mesin."

    def collect(self, query: dict) -> Iterator[RawItem]:
        feeds: list[str] = list(query.get("feeds", []))
        raw_keywords = list(query.get("keywords", []))
        keywords = [k.lower() for k in raw_keywords]
        # Tanpa feed eksplisit tapi ada keyword → cari via Google News RSS (gratis).
        if not feeds and raw_keywords:
            feeds = google_news_feeds(raw_keywords)

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

"""Adapter Blog — feed autodiscovery + ekstraksi teks penuh.

Beda dengan adapter RSS: RSS memakai ringkasan di dalam feed (murah, dangkal),
sedangkan Blog menemukan feed dari URL beranda lalu MENGAMBIL TEKS PENUH tiap
tulisan — yang dibutuhkan untuk analisis narasi panjang.

query = {
    "sites": ["https://blog.example.id"],   # beranda; feed dideteksi otomatis
    "feeds": ["https://blog.example.id/feed"],  # atau langsung
    "keywords": ["stimulus"],
    "max_posts": 50,
}
"""

import re
from collections.abc import Iterator
from urllib.parse import urljoin

import feedparser
import httpx

from workers.adapters.base import BaseAdapter, RawItem
from workers.adapters.web_extract import USER_AGENT, fetch_and_extract, fetch_html

_FEED_LINK_RE = re.compile(
    r"""<link[^>]+type=["']application/(?:rss|atom)\+xml["'][^>]*>""", re.IGNORECASE
)
_HREF_RE = re.compile(r"""href=["']([^"']+)["']""", re.IGNORECASE)


class BlogAdapter(BaseAdapter):
    platform = "blog"
    tier = "free"
    requires_credentials = False
    rate_note = "Autodiscovery feed + jeda 1 detik antar tulisan; batas default 50 tulisan."
    legal_note = "Menghormati robots.txt; hanya konten publik."

    def collect(self, query: dict) -> Iterator[RawItem]:
        max_posts = int(query.get("max_posts", 50))
        keywords = [k.lower() for k in query.get("keywords", [])]

        feeds: list[str] = list(query.get("feeds", []))
        for site in query.get("sites", []):
            feeds.extend(discover_feeds(site))

        emitted = 0
        seen: set[str] = set()
        for feed_url in dict.fromkeys(feeds):
            try:
                resp = httpx.get(
                    feed_url, headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True
                )
                resp.raise_for_status()
            except httpx.HTTPError:
                continue

            for entry in feedparser.parse(resp.content).entries:
                if emitted >= max_posts:
                    return
                link = entry.get("link")
                if not link or link in seen:
                    continue
                seen.add(link)

                extracted = fetch_and_extract(link)
                if extracted is None:
                    continue
                text = extracted["text"]
                if keywords and not any(k in text.lower() for k in keywords):
                    continue

                title = extracted["title"] or entry.get("title") or link
                yield RawItem(
                    platform=self.platform,
                    external_id=str(entry.get("id") or link)[:255],
                    author=extracted["author"] or entry.get("author") or feed_url,
                    content=f"{title}\n\n{text}",
                    url=link,
                    published_at=extracted["date"],
                    title=title,
                    raw={"feed": feed_url, "link": link, "title": title},
                )
                emitted += 1


def discover_feeds(site_url: str) -> list[str]:
    """Temukan URL feed dari <link rel=alternate> di beranda, plus tebakan lazim."""
    html = fetch_html(site_url)
    found: list[str] = []
    if html:
        for tag in _FEED_LINK_RE.findall(html):
            href = _HREF_RE.search(tag)
            if href:
                found.append(urljoin(site_url, href.group(1)))
    if not found:
        found = [urljoin(site_url, path) for path in ("/feed", "/rss.xml", "/atom.xml", "/feed.xml")]
    return found

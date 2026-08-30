"""Adapter News — penemuan artikel via GDELT DOC 2.0, ekstraksi via trafilatura.

GDELT DOC 2.0 gratis, tanpa API key, dan mengindeks berita dalam 65 bahasa
(termasuk Indonesia) — jadi ini jalur penemuan berita terluas yang legal dan
tanpa biaya. GDELT hanya memberi METADATA + URL, bukan teks penuh; teks diambil
tahap kedua lewat `web_extract` (hormat robots.txt).

query = {
    "keywords": ["stimulus pangan", ...],   # digabung OR
    "timespan": "7d",                       # 24h | 7d | 1m ...
    "country": "ID",                        # opsional, kode negara sumber GDELT
    "language": "indonesian",               # opsional
    "max_records": 250,                     # maks GDELT per panggilan
    "fetch_full_text": true,                # false = judul saja (hemat, tanpa crawl)
}
"""

from collections.abc import Iterator
from datetime import datetime

import httpx

from workers.adapters.base import BaseAdapter, RawItem
from workers.adapters.web_extract import USER_AGENT, fetch_and_extract

GDELT_DOC = "https://api.gdeltproject.org/api/v2/doc/doc"


class NewsAdapter(BaseAdapter):
    platform = "news"
    tier = "free"
    requires_credentials = False
    rate_note = "GDELT tanpa API key; maks 250 artikel/panggilan. Ekstraksi teks penuh diberi jeda per host."
    legal_note = "GDELT mengindeks berita publik. Ekstraksi teks menghormati robots.txt."

    def collect(self, query: dict) -> Iterator[RawItem]:
        keywords = query.get("keywords", [])
        if not keywords:
            return
        q = " OR ".join(f'"{k}"' if " " in k else k for k in keywords)
        if query.get("country"):
            q += f" sourcecountry:{query['country']}"
        if query.get("language"):
            q += f" sourcelang:{query['language']}"

        params = {
            "query": q,
            "mode": "artlist",
            "format": "json",
            "maxrecords": min(int(query.get("max_records", 250)), 250),
            "timespan": _gdelt_timespan(query.get("timespan", "1m")),
        }
        articles: list = []
        try:
            resp = httpx.get(
                GDELT_DOC, params=params, headers={"User-Agent": USER_AGENT}, timeout=60
            )
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
        except (httpx.HTTPError, ValueError):
            articles = []

        if not articles:
            # GDELT tak terjangkau/kosong (mis. jaringan memblok) → fallback Google
            # News RSS (gratis, keyword-searchable), agar 'news' tetap produktif.
            yield from self._google_news_fallback(keywords)
            return

        fetch_full = query.get("fetch_full_text", True)
        for art in articles:
            url = art.get("url")
            title = (art.get("title") or "").strip()
            if not url or not title:
                continue

            text = title
            author = art.get("domain", "unknown")
            published = _parse_seendate(art.get("seendate"))

            if fetch_full:
                extracted = fetch_and_extract(url)
                if extracted:
                    text = f"{extracted['title'] or title}\n\n{extracted['text']}"
                    author = extracted["author"] or author
                    published = extracted["date"] or published

            yield RawItem(
                platform=self.platform,
                external_id=url[:255],
                author=author,
                content=text,
                url=url,
                published_at=published,
                title=title,
                raw=art,
            )

    def _google_news_fallback(self, keywords: list[str]) -> Iterator[RawItem]:
        """Feed Google News RSS dari keyword (dipakai bila GDELT gagal/kosong)."""
        import feedparser

        from workers.adapters.rss import USER_AGENT as RSS_UA
        from workers.adapters.rss import google_news_feeds

        feeds = google_news_feeds(keywords)
        if not feeds:
            return
        try:
            resp = httpx.get(feeds[0], headers={"User-Agent": RSS_UA}, timeout=30, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError:
            return
        for entry in feedparser.parse(resp.content).entries:
            title = (entry.get("title") or "").strip()
            summary = entry.get("summary") or ""
            text = f"{title}. {summary}".strip(". ")
            ext = entry.get("id") or entry.get("link") or title
            if not ext or not text:
                continue
            yield RawItem(
                platform=self.platform, external_id=str(ext)[:255],
                author=entry.get("author") or "Google News", content=text,
                url=entry.get("link"), published_at=None, title=title, raw={},
            )


def _gdelt_timespan(ts: str) -> str:
    """GDELT DOC menerima maks ~3 bulan; ubah 'Nd' besar → '3m' agar tak ditolak."""
    import re

    m = re.fullmatch(r"(\d+)d", str(ts).strip())
    if m and int(m.group(1)) > 90:
        return "3m"
    return str(ts)


def _parse_seendate(value: str | None) -> datetime | None:
    if not value:
        return None
    try:  # format GDELT: 20260829T101500Z
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ")
    except ValueError:
        return None

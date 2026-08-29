"""Adapter Website — crawl terbatas atas domain tertentu.

Penemuan URL: sitemap.xml (disukai — murah & sopan) atau daftar URL langsung.
Ekstraksi: trafilatura. Selalu menghormati robots.txt.

Sengaja BUKAN crawler rekursif tak terbatas: OSINT butuh sumber terarah, dan
crawl dalam tanpa batas adalah risiko legal sekaligus operasional.

query = {
    "sitemaps": ["https://situs.id/sitemap.xml"],
    "urls": ["https://situs.id/artikel/1"],       # alternatif/ tambahan
    "keywords": ["stimulus"],                      # filter pada teks hasil ekstraksi
    "max_pages": 100,
}
"""

import re
from collections.abc import Iterator

import httpx

from workers.adapters.base import BaseAdapter, RawItem
from workers.adapters.web_extract import USER_AGENT, fetch_and_extract, robots_allowed

_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)


class WebsiteAdapter(BaseAdapter):
    platform = "website"
    tier = "free"
    requires_credentials = False
    rate_note = "Jeda 1 detik antar halaman; batas default 100 halaman per run."
    legal_note = (
        "Menghormati robots.txt dan tidak menembus autentikasi/paywall (PRD §14). "
        "Scraping hanya untuk situs tanpa API resmi."
    )

    def collect(self, query: dict) -> Iterator[RawItem]:
        max_pages = int(query.get("max_pages", 100))
        keywords = [k.lower() for k in query.get("keywords", [])]

        urls: list[str] = list(query.get("urls", []))
        for sitemap in query.get("sitemaps", []):
            urls.extend(self._urls_from_sitemap(sitemap, limit=max_pages))

        seen: set[str] = set()
        emitted = 0
        for url in urls:
            if emitted >= max_pages or url in seen:
                continue
            seen.add(url)

            extracted = fetch_and_extract(url)
            if extracted is None:
                continue
            text = extracted["text"]
            if keywords and not any(k in text.lower() for k in keywords):
                continue

            title = extracted["title"] or url
            yield RawItem(
                platform=self.platform,
                external_id=url[:255],
                author=extracted["author"] or _domain(url),
                content=f"{title}\n\n{text}",
                url=url,
                published_at=extracted["date"],
                title=title,
                raw={"url": url, "title": title, "author": extracted["author"]},
            )
            emitted += 1

    def _urls_from_sitemap(self, sitemap_url: str, limit: int) -> list[str]:
        if not robots_allowed(sitemap_url):
            return []
        try:
            resp = httpx.get(
                sitemap_url, headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

        locs = _LOC_RE.findall(resp.text)
        # Sitemap index → turun satu tingkat, tidak lebih dalam
        if locs and all(loc.endswith(".xml") for loc in locs[:3]):
            nested: list[str] = []
            for child in locs[:5]:
                nested.extend(self._urls_from_sitemap(child, limit=limit))
                if len(nested) >= limit:
                    break
            return nested[:limit]
        return locs[:limit]


def _domain(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).netloc or "unknown"

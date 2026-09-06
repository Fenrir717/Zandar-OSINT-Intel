"""Adapter Sitemap — koleksi BULK arsip situs via sitemap.xml (jalur patuh).

Portal berita Indonesia (Detik, Kompas, Suara, Merdeka, Tribun, dll.) mengekspos
sitemap publik — memang DITUJUKAN untuk crawler mesin pencari. Adapter ini:
menelusuri sitemap (termasuk sitemap-index bertingkat + .gz), memfilter per
tanggal/keyword, lalu mengekstrak teks artikel via trafilatura (hormat robots.txt).

Ini BUKAN scraping gerilya: sitemap = undangan resmi untuk mengindeks; tanpa
signature-spoofing / proxy-evasion. Volume besar (arsip penuh) + genuinely Indonesia
+ legal. Untuk kedalaman historis lintas waktu, pasangkan dgn adapter `wayback`.

query = {
    "url": "https://www.suara.com",        # root situs ATAU URL sitemap langsung, WAJIB
    "sitemap": "https://.../sitemap.xml",   # opsional: paksa sitemap tertentu
    "keywords": ["laundry", "stimulus"],    # opsional filter
    "match": "url",                          # "url" (murah, cek slug) | "text" (ekstrak dulu)
    "from": "2026-01-01", "to": "2026-12-31",  # opsional filter lastmod (YYYY-MM-DD)
    "max_urls": 5000,                        # cap enumerasi URL (keluasan)
    "max_articles": 200,                     # cap ekstraksi (biaya/waktu)
    "delay": 0.3,                            # jeda sopan antar-ekstraksi
}
"""

import gzip
import time
from collections.abc import Iterator
from datetime import date, datetime
from urllib.parse import urljoin, urlparse

import httpx
from lxml import etree

from workers.adapters.base import AdapterNotConfigured, BaseAdapter, RawItem
from workers.adapters.web_extract import USER_AGENT, fetch_and_extract

_MAX_URLS_CAP = 50000
_MAX_ARTICLES_CAP = 5000
_MAX_CHILD_SITEMAPS = 60      # batas sitemap anak yang ditelusuri (sitemap-index)
_COMMON_PATHS = ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-news.xml", "/news-sitemap.xml")


class SitemapAdapter(BaseAdapter):
    platform = "sitemap"
    key = "sitemap"
    tier = "free"
    requires_credentials = False
    rate_note = "Sitemap publik + ekstraksi trafilatura berjeda; tanpa proxy/evasion."
    legal_note = "Sitemap ditujukan untuk crawler; ekstraksi menghormati robots.txt."

    def collect(self, query: dict) -> Iterator[RawItem]:
        root = query.get("url")
        if not root:
            raise AdapterNotConfigured("Sitemap butuh 'url' (root situs / URL sitemap) pada query")

        keywords = [k.lower() for k in query.get("keywords", [])]
        match = (query.get("match") or "url").lower()
        d_from = _parse_date(query.get("from"))
        d_to = _parse_date(query.get("to"))
        max_urls = max(1, min(int(query.get("max_urls", 5000)), _MAX_URLS_CAP))
        max_articles = max(1, min(int(query.get("max_articles", 200)), _MAX_ARTICLES_CAP))
        delay = max(0.0, float(query.get("delay", 0.3)))

        seeds = [query["sitemap"]] if query.get("sitemap") else self._discover(root)
        if not seeds:
            return

        # Kumpulkan (loc, lastmod) menembus sitemap-index bertingkat, sampai max_urls.
        candidates = list(self._walk(seeds, max_urls))
        # Filter tanggal (lastmod) + keyword-di-URL (murah) bila match=url.
        picked = []
        for loc, lastmod in candidates:
            if (d_from or d_to) and lastmod:
                ld = _parse_date(lastmod)
                if ld and ((d_from and ld < d_from) or (d_to and ld > d_to)):
                    continue
            if keywords and match == "url" and not any(k in loc.lower() for k in keywords):
                continue
            picked.append((loc, lastmod))

        if not picked:
            return
        # Sampling merata → sebar lintas arsip (bukan hanya N teratas).
        want = max_articles if match == "url" else max_articles * 3
        picked = _stride_sample(picked, min(len(picked), want))

        emitted = 0
        for loc, lastmod in picked:
            if emitted >= max_articles:
                break
            extracted = fetch_and_extract(loc)  # trafilatura + hormat robots.txt
            if delay:
                time.sleep(delay)
            if extracted is None:
                continue
            text = extracted["text"]
            if keywords and match == "text" and not any(k in text.lower() for k in keywords):
                continue
            title = extracted["title"] or _url_label(loc)
            published = extracted["date"] or _parse_dt(lastmod)
            emitted += 1
            yield RawItem(
                platform=self.platform,
                external_id=loc[:255],
                author=extracted["author"] or _domain(loc),
                content=f"{title}\n\n{text}",
                url=loc,
                published_at=published,
                title=title,
                raw={"loc": loc, "lastmod": lastmod, "source": "sitemap"},
            )

    def _discover(self, root: str) -> list[str]:
        """Temukan sitemap: robots.txt 'Sitemap:' → jalur umum sebagai fallback."""
        if root.endswith(".xml") or root.endswith(".xml.gz"):
            return [root]
        found: list[str] = []
        robots = _fetch(urljoin(root, "/robots.txt"))
        if robots:
            for line in robots.decode("utf-8", "ignore").splitlines():
                if line.lower().startswith("sitemap:"):
                    found.append(line.split(":", 1)[1].strip())
        if not found:
            found = [urljoin(root, p) for p in _COMMON_PATHS]
        return found

    def _walk(self, seeds: list[str], max_urls: int) -> Iterator[tuple[str, str | None]]:
        """BFS sitemap-index → yield (loc, lastmod) URL artikel, dibatasi max_urls."""
        queue = list(seeds)
        visited: set[str] = set()
        child_count = 0
        seen_urls = 0
        while queue and seen_urls < max_urls:
            sm = queue.pop(0)
            if sm in visited:
                continue
            visited.add(sm)
            data = _fetch(sm)
            if not data:
                continue
            parsed = _parse_sitemap(data)
            if parsed is None:
                continue
            is_index, entries = parsed
            if is_index:
                for loc, _lm in entries:
                    if loc and child_count < _MAX_CHILD_SITEMAPS:
                        queue.append(loc)
                        child_count += 1
            else:
                for loc, lastmod in entries:
                    if loc:
                        yield loc, lastmod
                        seen_urls += 1
                        if seen_urls >= max_urls:
                            return


def _fetch(url: str) -> bytes | None:
    try:
        r = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=45, follow_redirects=True)
        r.raise_for_status()
        data = r.content
    except (httpx.HTTPError, OSError):
        return None
    if url.endswith(".gz") or data[:2] == b"\x1f\x8b":
        try:
            data = gzip.decompress(data)
        except OSError:
            return None
    return data


def _parse_sitemap(data: bytes) -> tuple[bool, list[tuple[str, str | None]]] | None:
    """→ (is_index, [(loc, lastmod)]) atau None bila bukan XML sitemap valid."""
    try:
        root = etree.fromstring(data)  # noqa: S320 — sumber tepercaya (sitemap portal), bukan XXE vektor
    except etree.XMLSyntaxError:
        return None
    is_index = etree.QName(root).localname == "sitemapindex"
    out: list[tuple[str, str | None]] = []
    for el in root:
        loc = lastmod = None
        for child in el:
            ln = etree.QName(child).localname
            if ln == "loc":
                loc = (child.text or "").strip()
            elif ln == "lastmod":
                lastmod = (child.text or "").strip()
        if loc:
            out.append((loc, lastmod))
    return is_index, out


def _stride_sample(items: list, n: int) -> list:
    total = len(items)
    if n >= total:
        return items
    if n <= 0:
        return []
    step = total / n
    return [items[int(i * step)] for i in range(n)]


def _parse_date(value: str | None) -> date | None:
    dt = _parse_dt(value)
    return dt.date() if dt else None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value)[:10], fmt)
        except ValueError:
            continue
    return None


def _url_label(url: str) -> str:
    path = urlparse(url).path.strip("/")
    seg = path.split("/")[-1] if path else ""
    seg = seg.rsplit(".", 1)[0].replace("-", " ").replace("_", " ").strip()
    return seg[:120] if seg else _domain(url)


def _domain(url: str) -> str:
    return urlparse(url if "//" in url else "http://" + url).netloc or "unknown"

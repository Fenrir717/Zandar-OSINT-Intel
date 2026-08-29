"""Ekstraksi artikel bersama untuk semua adapter berbasis halaman web
(news, blog, website, dan fallback rss).

Alasan modul ini ada: "News", "Blog", "Website", dan "RSS" berbeda hanya pada
cara MENEMUKAN URL — cara MENGAMBIL TEKS-nya identik. Menyalin logika ekstraksi
ke empat adapter berarti menyalin bug-nya juga.

Ekstraksi memakai trafilatura (F1 ~0.94 pada benchmark ekstraksi konten utama,
aktif dirawat — berbeda dengan newspaper3k yang berhenti sejak 2018).
"""

import time
import urllib.robotparser as robotparser
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura

USER_AGENT = "ZandarOSINT/0.1 (+riset OSINT; hubungi pemilik repo)"
_ROBOTS_CACHE: dict[str, robotparser.RobotFileParser | None] = {}


def robots_allowed(url: str, user_agent: str = USER_AGENT) -> bool:
    """Patuhi robots.txt (PRD §14: scraping hanya untuk sumber tanpa API,
    menghormati robots.txt dan crawl delay). Gagal-terbuka bila robots.txt
    tidak terjangkau — sama seperti perilaku crawler umumnya."""
    parts = urlparse(url)
    if not parts.scheme or not parts.netloc:
        return False
    origin = f"{parts.scheme}://{parts.netloc}"

    if origin not in _ROBOTS_CACHE:
        parser = robotparser.RobotFileParser()
        try:
            resp = httpx.get(
                urljoin(origin, "/robots.txt"),
                headers={"User-Agent": user_agent},
                timeout=15,
                follow_redirects=True,
            )
            if resp.status_code >= 400:
                _ROBOTS_CACHE[origin] = None
            else:
                parser.parse(resp.text.splitlines())
                _ROBOTS_CACHE[origin] = parser
        except httpx.HTTPError:
            _ROBOTS_CACHE[origin] = None

    parser = _ROBOTS_CACHE[origin]
    return True if parser is None else parser.can_fetch(user_agent, url)


def fetch_html(url: str, timeout: int = 30) -> str | None:
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        return None
    if "html" not in resp.headers.get("content-type", "text/html"):
        return None
    return resp.text


def extract_article(html: str, url: str | None = None) -> dict | None:
    """Kembalikan {title, text, author, date} atau None bila bukan artikel."""
    data = trafilatura.extract(
        html,
        url=url,
        output_format="json",
        with_metadata=True,
        include_comments=False,
        favor_precision=True,
    )
    if not data:
        return None

    import json

    try:
        parsed = json.loads(data)
    except (ValueError, TypeError):
        return None

    text = (parsed.get("text") or "").strip()
    if len(text) < 120:  # halaman indeks/navigasi, bukan artikel
        return None
    return {
        "title": (parsed.get("title") or "").strip() or None,
        "text": text,
        "author": (parsed.get("author") or "").strip() or None,
        "date": _parse_date(parsed.get("date")),
    }


def fetch_and_extract(url: str, respect_robots: bool = True, delay: float = 1.0) -> dict | None:
    """Satu URL → artikel terekstrak. Mengembalikan None bila diblokir/gagal/bukan artikel."""
    if respect_robots and not robots_allowed(url):
        return None
    html = fetch_html(url)
    if delay:
        time.sleep(delay)  # sopan terhadap host
    if html is None:
        return None
    return extract_article(html, url=url)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None

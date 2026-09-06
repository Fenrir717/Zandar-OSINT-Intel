"""Adapter App Store (iOS) — review aplikasi via endpoint publik Apple.

Melengkapi `playstore` untuk sisi iOS. Dua endpoint publik gratis, tanpa key:
  - iTunes Search API   → cari app id (trackId) dari nama brand
  - RSS customer reviews → review terbaru (bintang + teks), ~50/halaman, hingga 10 hal

query = {
    "app_ids": [944875099, ...],   # trackId numerik (opsional)
    "keywords": ["gojek"],         # opsional → cari app dari nama brand
    "max_apps": 3,
    "count": 200,                  # review terbaru per app (dibulatkan per 50)
    "country": "id",
}

Skor bintang di `raw.score`. Data publik; penulis di-hash saat enrichment.
"""

from collections.abc import Iterator
from datetime import datetime

import httpx

from workers.adapters.base import BaseAdapter, RawItem

_UA = {"User-Agent": "Mozilla/5.0 (compatible; ZandarOSINT/0.1; +research)"}
_SEARCH = "https://itunes.apple.com/search"


def _lbl(x) -> str:
    """Ambil 'label' dari node RSS JSON Apple (mis. {'label': '5'})."""
    return x.get("label", "") if isinstance(x, dict) else (x or "")


class AppStoreAdapter(BaseAdapter):
    platform = "appstore"
    tier = "free"
    requires_credentials = False
    rate_note = "Endpoint publik Apple (Search + RSS reviews); ~50 review/halaman, maks 10 hal."
    legal_note = "Review publik. Penulis di-hash saat enrichment (UU PDP)."

    def collect(self, query: dict) -> Iterator[RawItem]:
        country = (query.get("country") or "id").lower()
        count = min(int(query.get("count", 200)), 500)
        max_apps = int(query.get("max_apps", 3))

        app_ids = [str(a) for a in query.get("app_ids", []) if a]
        if not app_ids and query.get("keywords"):
            app_ids = self._search_apps(query["keywords"], country, max_apps)

        pages = max(1, min((count + 49) // 50, 10))  # RSS: 50/hal, maks 10 hal
        for app_id in app_ids:
            app_url = f"https://apps.apple.com/{country}/app/id{app_id}"
            emitted = 0
            for page in range(1, pages + 1):
                url = (f"https://itunes.apple.com/{country}/rss/customerreviews/"
                       f"page={page}/id={app_id}/sortby=mostrecent/json")
                try:
                    resp = httpx.get(url, headers=_UA, timeout=30)
                    resp.raise_for_status()
                    entries = resp.json().get("feed", {}).get("entry", [])
                except (httpx.HTTPError, ValueError):
                    break  # app tak ada / jaringan — hentikan halaman app ini
                revs = [e for e in entries if isinstance(e, dict) and "im:rating" in e]
                if not revs:
                    break  # habis review
                for e in revs:
                    if emitted >= count:
                        break
                    rid = _lbl(e.get("id"))
                    title = _lbl(e.get("title"))
                    body = _lbl(e.get("content"))
                    text = f"{title}. {body}".strip(". ") if title else body
                    if not rid or not text:
                        continue
                    yield RawItem(
                        platform=self.platform,
                        external_id=str(rid)[:255],
                        author=_lbl((e.get("author") or {}).get("name")) or "anon",
                        content=text,
                        url=app_url,
                        published_at=_parse_dt(_lbl(e.get("updated"))),
                        raw={
                            "app_id": app_id,
                            "score": int(_lbl(e.get("im:rating")) or 0) or None,
                            "app_version": _lbl(e.get("im:version")),
                            "votes": _lbl(e.get("im:voteCount")),
                        },
                    )
                    emitted += 1
                if emitted >= count:
                    break

    def _search_apps(self, keywords: list, country: str, max_apps: int) -> list[str]:
        term = " ".join(str(k) for k in keywords[:3])[:100]
        try:
            r = httpx.get(_SEARCH, params={"term": term, "country": country,
                                           "entity": "software", "limit": max_apps},
                          headers=_UA, timeout=25)
            r.raise_for_status()
            return [str(a["trackId"]) for a in r.json().get("results", []) if a.get("trackId")]
        except (httpx.HTTPError, ValueError):
            return []


def _parse_dt(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

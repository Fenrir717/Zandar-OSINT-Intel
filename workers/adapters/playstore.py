"""Adapter Google Play — review aplikasi (sinyal reputasi terstruktur).

Review = inti reputasi bisnis: **rating bintang + keluhan/pujian nyata**, jauh lebih
relevan untuk analisis reputasi daripada cuitan mentah. Data publik (logged-out) —
scraping data publik dipertahankan hukum (hiQ; Meta v. Bright Data 2024); identitas
penulis di-pseudonim-kan (HMAC) saat enrichment.

query = {
    "app_ids": ["com.tokopedia.tkpd", ...],  # opsional (langsung)
    "keywords": ["tokopedia"],               # opsional → cari app dari nama brand
    "max_apps": 3,                           # batas app hasil pencarian keyword
    "count": 200,                            # review terbaru per app
    "lang": "id", "country": "id",
}

Skor bintang (1-5) disimpan di `raw.score` — sinyal reputasi langsung, terpisah dari
sentimen teks yang dihitung classifier. Keyword-capable: cari brand → app → review.
"""

from collections.abc import Iterator

from workers.adapters.base import BaseAdapter, RawItem


class PlayStoreAdapter(BaseAdapter):
    platform = "playstore"
    tier = "free"
    requires_credentials = False
    rate_note = "Endpoint publik Google Play; review terbaru per app. Rating bintang + teks."
    legal_note = "Review publik (logged-out). Penulis di-hash saat enrichment (UU PDP)."

    def collect(self, query: dict) -> Iterator[RawItem]:
        try:
            from google_play_scraper import Sort, reviews, search
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Adapter playstore butuh google-play-scraper: pip install google-play-scraper"
            ) from exc

        lang = query.get("lang", "id")
        country = query.get("country", "id")
        count = min(int(query.get("count", 200)), 2000)
        max_apps = int(query.get("max_apps", 3))

        # Tentukan daftar app: eksplisit, atau cari dari nama brand (keyword).
        app_ids = [a for a in query.get("app_ids", []) if a]
        if not app_ids and query.get("keywords"):
            kw = " ".join(str(k) for k in query["keywords"][:3])[:100]
            try:
                hits = search(kw, lang=lang, country=country, n_hits=max_apps + 3)
            except Exception:
                hits = []
            # hit teratas kadang appId=None (kartu "top result") → saring
            app_ids = [h["appId"] for h in hits if h.get("appId")][:max_apps]

        for app_id in app_ids:
            app_url = f"https://play.google.com/store/apps/details?id={app_id}"
            try:
                rv, _ = reviews(app_id, lang=lang, country=country, sort=Sort.NEWEST, count=count)
            except Exception:
                continue  # app tak ada / jaringan gagal — lanjut app lain (tak meledak)

            for r in rv:
                text = (r.get("content") or "").strip()
                rid = r.get("reviewId")
                if not text or not rid:
                    continue
                yield RawItem(
                    platform=self.platform,
                    external_id=str(rid)[:255],
                    author=r.get("userName") or "anon",
                    content=text,
                    url=app_url,
                    published_at=r.get("at"),
                    raw={
                        "app_id": app_id,
                        "score": r.get("score"),  # bintang 1-5 (sinyal reputasi langsung)
                        "thumbs_up": r.get("thumbsUpCount"),
                        "app_version": r.get("reviewCreatedVersion") or r.get("appVersion"),
                        "reply": r.get("replyContent"),
                    },
                )

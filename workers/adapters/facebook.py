"""Adapter Facebook — post/komentar PUBLIK via facebook-scraper (request polos).

facebook-scraper mengakses antarmuka web publik FB (mobile) dgn request polos (Python
requests) — BUKAN evasion (tanpa proxy/spoofing). Ambil post halaman/grup publik +
komentar.

Batas JUJUR (dari README tool): FB agresif blokir → "scrape terlalu banyak, IP bisa
di-ban sementara". Banyak field bisa `None`; grup sering cuma 1 halaman. Reliabilitas
naik dgn COOKIE login akun-mu sendiri (opsional, config) — risikomu. Kita TIDAK tambah
proxy/rotasi utk menembus blokir. Untuk volume FB andal → vendor.

query = {
    "pages": ["BankBCA", ...],   # nama/username halaman publik (atau ID grup publik)
    "max_pages": 5,               # halaman feed (tiap halaman ~beberapa post)
    "with_comments": false,       # ambil komentar? (lebih berat)
    "cookies": "path/cookies.txt", # opsional: cookie login akun sendiri (netscape/json)
}
"""

from collections.abc import Iterator

from workers.adapters.base import AdapterNotConfigured, BaseAdapter, RawItem

_MAX_PAGES_CAP = 50


class FacebookAdapter(BaseAdapter):
    platform = "facebook"
    key = "facebook"
    tier = "free"
    requires_credentials = False
    rate_note = "Request polos ke web FB publik; FB bisa IP-ban bila agresif. Tanpa proxy/spoofing."
    legal_note = "Hanya halaman/grup publik. Cookie login (opsional) = akun sendiri, risiko ban."

    def collect(self, query: dict) -> Iterator[RawItem]:
        try:
            from facebook_scraper import get_posts  # lazy
        except ImportError as exc:
            raise AdapterNotConfigured('facebook-scraper belum terpasang: pip install -e ".[social]"') from exc

        pages = [p for p in (query.get("pages") or []) if p]
        if not pages:
            raise AdapterNotConfigured("Facebook butuh 'pages' (halaman/grup publik) pada query")

        max_pages = max(1, min(int(query.get("max_pages", 5)), _MAX_PAGES_CAP))
        cookies = query.get("cookies")  # opsional: akun sendiri
        with_comments = bool(query.get("with_comments", False))
        opts = {"comments": with_comments, "reactions": False}

        for page in pages:
            try:
                for post in get_posts(page, pages=max_pages, cookies=cookies, options=opts):
                    yield from self._emit_post(post, page, with_comments)
            except Exception:  # noqa: BLE001 — FB blokir/ban/berubah → berhenti sopan per-halaman
                continue

    def _emit_post(self, post: dict, page: str, with_comments: bool):
        pid = post.get("post_id")
        text = (post.get("text") or "").strip()
        author = post.get("username") or post.get("user_id") or page
        if pid and text:
            yield RawItem(
                platform=self.platform,
                external_id=f"fb:{pid}"[:255],
                author=str(author),
                content=text,
                url=post.get("post_url"),
                published_at=post.get("time"),
                raw={"post_id": pid, "likes": post.get("likes"),
                     "comments": post.get("comments"), "shares": post.get("shares")},
            )
        if with_comments:
            for c in (post.get("comments_full") or []):
                ctext = (c.get("comment_text") or "").strip()
                cid = c.get("comment_id")
                if not ctext or not cid:
                    continue
                yield RawItem(
                    platform=self.platform,
                    external_id=f"fb:c:{cid}"[:255],
                    author=str(c.get("commenter_name") or "unknown"),
                    content=ctext,
                    url=c.get("comment_url") or post.get("post_url"),
                    published_at=c.get("comment_time"),
                    raw={"comment_id": cid, "post_id": pid},
                )

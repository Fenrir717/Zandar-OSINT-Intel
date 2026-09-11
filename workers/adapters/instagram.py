"""Adapter Instagram — data PUBLIK via Instaloader (request polos, tanpa evasion).

Instaloader = tool matang untuk data Instagram publik (profil, post, caption, komentar).
Request polos + rate-limit bawaan (sopan), BUKAN TLS-spoof/rotasi-proxy. Hanya konten
publik.

Batas JUJUR: tanpa login, Instagram me-rate-limit/blokir agresif → volume KECIL, sering
401/challenge. Bisa pakai SESSION login akun-mu sendiri (opsional, config `session_file`)
— risikomu (akun bisa kena batasi). Kita TIDAK tambah proxy/rotasi utk menembus blokir;
kalau diblok, berhenti sopan. Untuk volume IG andal → vendor (Scrapfly/Apify).

query = {
    "profiles": ["bankbca", ...],     # username publik
    "hashtag": "bca",                  # ATAU hashtag (tanpa #)
    "max_posts": 30,                   # batas post per target
    "with_comments": false,            # ambil komentar? (lebih banyak request → rawan limit)
    "max_comments": 20,
    "session_file": "path",            # opsional: sesi login akun sendiri (dibuat manual)
}
"""

from collections.abc import Iterator

from workers.adapters.base import AdapterNotConfigured, BaseAdapter, RawItem

_MAX_POSTS_CAP = 300


class InstagramAdapter(BaseAdapter):
    platform = "instagram"
    key = "instagram"
    tier = "free"
    requires_credentials = False
    rate_note = "Instaloader request polos + rate-limit bawaan. Tanpa login → volume kecil/rawan 401."
    legal_note = "Hanya konten publik. Login (opsional) = akun sendiri, risiko batasi akun."

    def collect(self, query: dict) -> Iterator[RawItem]:
        try:
            import instaloader  # lazy
        except ImportError as exc:
            raise AdapterNotConfigured('Instaloader belum terpasang: pip install -e ".[social]"') from exc

        profiles = [p for p in (query.get("profiles") or []) if p]
        hashtag = query.get("hashtag")
        if not profiles and not hashtag:
            raise AdapterNotConfigured("Instagram butuh 'profiles' atau 'hashtag' pada query")

        max_posts = max(1, min(int(query.get("max_posts", 30)), _MAX_POSTS_CAP))
        with_comments = bool(query.get("with_comments", False))
        max_comments = max(0, int(query.get("max_comments", 20)))

        loader = instaloader.Instaloader(
            download_pictures=False, download_videos=False, download_video_thumbnails=False,
            download_geotags=False, save_metadata=False, compress_json=False, quiet=True,
        )
        sess = query.get("session_file")
        if sess:
            try:
                loader.load_session_from_file(query.get("login_user", ""), sess)
            except Exception:  # noqa: BLE001 — sesi invalid → lanjut anonim
                pass

        try:
            if hashtag:
                posts = instaloader.Hashtag.from_name(loader.context, str(hashtag).lstrip("#")).get_posts()
                yield from self._emit(posts, None, max_posts, with_comments, max_comments)
            for uname in profiles:
                prof = instaloader.Profile.from_username(loader.context, uname)
                yield from self._emit(prof.get_posts(), uname, max_posts, with_comments, max_comments)
        except Exception:  # noqa: BLE001 — IG blokir/rate-limit → berhenti sopan
            return

    def _emit(self, posts, uname, max_posts, with_comments, max_comments):
        count = 0
        for post in posts:
            if count >= max_posts:
                break
            caption = (post.caption or "").strip()
            author = uname or getattr(post, "owner_username", None) or "unknown"
            if caption:
                count += 1
                yield RawItem(
                    platform=self.platform,
                    external_id=f"ig:{post.shortcode}"[:255],
                    author=author,
                    content=caption,
                    url=f"https://www.instagram.com/p/{post.shortcode}/",
                    published_at=post.date_utc,
                    raw={"shortcode": post.shortcode, "likes": post.likes, "comments": post.comments},
                )
            if with_comments:
                try:
                    for j, c in enumerate(post.get_comments()):
                        if j >= max_comments:
                            break
                        txt = (c.text or "").strip()
                        if not txt:
                            continue
                        yield RawItem(
                            platform=self.platform,
                            external_id=f"ig:c:{post.shortcode}:{c.id}"[:255],
                            author=getattr(c.owner, "username", "unknown"),
                            content=txt,
                            url=f"https://www.instagram.com/p/{post.shortcode}/",
                            published_at=getattr(c, "created_at_utc", None),
                            raw={"post": post.shortcode, "comment_id": c.id},
                        )
                except Exception:  # noqa: BLE001 — komentar rawan limit → lewati
                    continue

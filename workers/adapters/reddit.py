"""Adapter Reddit — endpoint JSON publik (tier non-komersial, 100 req/menit dgn OAuth).

query = {
    "subreddits": ["indonesia", ...],
    "keywords": ["stimulus", ...],
    "limit": 100,                    # per subreddit, maks 100 per halaman
    "max_pages": 3,                  # paginasi 'after' → tembus batas 100 (≤10 halaman)
    "sort": "new",
}
Fase 1: post via search.json publik + User-Agent deskriptif.
TODO Fase lanjut: OAuth (rate limit lebih baik) + tarik komentar per post.
"""

import time
from collections.abc import Iterator
from datetime import UTC, datetime

import httpx

from workers.adapters.base import BaseAdapter, RawItem

USER_AGENT = "windows:zandar-osint:v0.1 (research)"


class RedditAdapter(BaseAdapter):
    platform = "reddit"
    tier = "free"
    requires_credentials = False
    rate_note = "Endpoint JSON publik; jeda 2 detik antar subreddit. OAuth (100 req/menit) menyusul."
    legal_note = "Tier gratis hanya untuk penggunaan non-komersial; komersial butuh kontrak Reddit."

    def collect(self, query: dict) -> Iterator[RawItem]:
        keywords = query.get("keywords", [])
        q = " OR ".join(keywords) if keywords else "*"
        per_page = min(int(query.get("limit", 100)), 100)  # maks 100/halaman (batas Reddit)
        max_pages = max(1, min(int(query.get("max_pages", 3)), 10))  # paginasi 'after' → tembus 100
        sort = query.get("sort", "new")

        # Tiap target = (subreddit|None, restrict). Tanpa subreddit → pencarian
        # GLOBAL seluruh Reddit (scan keyword-only tetap dapat hasil).
        subs = query.get("subreddits", [])
        targets = [(s, 1) for s in subs] if subs else [(None, 0)]

        for sub, restrict in targets:
            url = f"https://www.reddit.com/r/{sub}/search.json" if sub else "https://www.reddit.com/search.json"
            after: str | None = None
            for _page in range(max_pages):
                params = {"q": q, "sort": sort, "limit": per_page}
                if restrict:
                    params["restrict_sr"] = 1
                if after:
                    params["after"] = after
                try:
                    resp = httpx.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
                    resp.raise_for_status()
                    data = resp.json().get("data", {})
                except (httpx.HTTPError, ValueError):
                    break

                children = data.get("children", [])
                if not children:
                    break
                for child in children:
                    post = child.get("data", {})
                    text = (post.get("title", "") + ". " + post.get("selftext", "")).strip(". ")
                    if not post.get("name") or not text:
                        continue
                    yield RawItem(
                        platform=self.platform,
                        external_id=post["name"],  # t3_xxxxx — stabil
                        author=post.get("author", "unknown"),
                        content=text,
                        url=f"https://www.reddit.com{post.get('permalink', '')}",
                        published_at=datetime.fromtimestamp(post.get("created_utc", 0), tz=UTC)
                        if post.get("created_utc")
                        else None,
                        raw=post,
                    )
                after = data.get("after")
                if not after:
                    break  # habis halaman
                time.sleep(1)  # sopan antar halaman
            time.sleep(2)  # jauh di bawah rate limit publik antar target

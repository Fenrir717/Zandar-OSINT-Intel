"""Adapter Reddit — endpoint JSON publik (tier non-komersial, 100 req/menit dgn OAuth).

query = {
    "subreddits": ["indonesia", ...],
    "keywords": ["stimulus", ...],
    "limit": 100,                    # per subreddit, maks 100 per halaman
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

    def collect(self, query: dict) -> Iterator[RawItem]:
        keywords = query.get("keywords", [])
        q = " OR ".join(keywords) if keywords else "*"
        limit = min(int(query.get("limit", 100)), 100)
        sort = query.get("sort", "new")

        for sub in query.get("subreddits", []):
            url = f"https://www.reddit.com/r/{sub}/search.json"
            try:
                resp = httpx.get(
                    url,
                    params={"q": q, "restrict_sr": 1, "sort": sort, "limit": limit},
                    headers={"User-Agent": USER_AGENT},
                    timeout=30,
                )
                resp.raise_for_status()
            except httpx.HTTPError:
                continue

            for child in resp.json().get("data", {}).get("children", []):
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
            time.sleep(2)  # jauh di bawah rate limit publik

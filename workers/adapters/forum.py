"""Adapter Forum — Discourse JSON API (publik, tanpa autentikasi).

Discourse dipilih sebagai target pertama karena sebagian besar forum komunitas
modern memakainya dan mengekspos endpoint JSON publik yang stabil
(`/search.json`, `/t/{id}.json`) — jauh lebih andal daripada scraping HTML yang
patah tiap kali markup berubah.

Forum non-Discourse (mis. Kaskus/phpBB) memakai adapter `website` dengan daftar
URL thread, atau menunggu parser khusus.

query = {
    "base_url": "https://forum.example.id",
    "keywords": ["stimulus"],
    "max_topics": 20,
    "include_replies": true,
}
"""

import html as html_mod
import re
import time
from collections.abc import Iterator
from datetime import datetime

import httpx

from workers.adapters.base import BaseAdapter, RawItem
from workers.adapters.web_extract import USER_AGENT

_TAG_RE = re.compile(r"<[^>]+>")


class ForumAdapter(BaseAdapter):
    platform = "forum"
    tier = "free"
    requires_credentials = False
    required_config = ()
    rate_note = "Endpoint JSON publik Discourse; jeda 1,5 detik antar permintaan."
    legal_note = "Hanya konten publik; tidak menembus login. Hormati ToS forum masing-masing."

    def collect(self, query: dict) -> Iterator[RawItem]:
        base = (query.get("base_url") or self.config.get("base_url") or "").rstrip("/")
        if not base:
            # Tanpa base_url forum spesifik, tak ada pencarian keyword universal →
            # fail-soft (0 item, bukan error), agar scan keyword-only tak gagal.
            return

        keywords = query.get("keywords", [])
        max_topics = int(query.get("max_topics", 60))
        include_replies = query.get("include_replies", True)

        topic_ids = self._search_topics(base, keywords, max_topics)
        for topic_id in topic_ids:
            yield from self._topic_posts(base, topic_id, include_replies)

    def _search_topics(self, base: str, keywords: list[str], limit: int) -> list[int]:
        if not keywords:
            url, params = f"{base}/latest.json", {}
        else:
            url, params = f"{base}/search.json", {"q": " ".join(keywords)}
        try:
            resp = httpx.get(
                url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30,
                follow_redirects=True,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            return []

        topics = data.get("topics") or data.get("topic_list", {}).get("topics", [])
        return [t["id"] for t in topics[:limit] if t.get("id")]

    def _topic_posts(self, base: str, topic_id: int, include_replies: bool) -> Iterator[RawItem]:
        try:
            resp = httpx.get(
                f"{base}/t/{topic_id}.json",
                headers={"User-Agent": USER_AGENT},
                timeout=30,
                follow_redirects=True,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            return
        finally:
            time.sleep(1.5)

        title = data.get("title", "")
        posts = data.get("post_stream", {}).get("posts", [])
        if not include_replies:
            posts = posts[:1]

        for post in posts:
            text = _strip_html(post.get("cooked", ""))
            if not text or not post.get("id"):
                continue
            yield RawItem(
                platform=self.platform,
                external_id=f"{base}#{post['id']}"[:255],
                author=post.get("username", "unknown"),
                content=text,
                url=f"{base}/t/{topic_id}/{post.get('post_number', 1)}",
                published_at=_parse_ts(post.get("created_at")),
                title=title,
                raw=post,
            )


def _strip_html(raw_html: str) -> str:
    return html_mod.unescape(_TAG_RE.sub(" ", raw_html)).strip()


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

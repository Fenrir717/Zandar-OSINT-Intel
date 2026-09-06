"""Adapter GitHub — issues, pull request, dan komentarnya via REST API resmi.

Relevan untuk investigasi bertema teknologi/keamanan siber: diskusi kerentanan,
keluhan pengguna atas produk, dan jejak aktor di repositori publik.

Batas resmi: 5.000 req/jam (token) untuk REST umum, tapi endpoint SEARCH jauh
lebih ketat — 30 req/menit — jadi pencarian dilakukan berhalaman besar dan
pengambilan komentar dibatasi eksplisit.

query = {
    "search": "ransomware in:title",     # sintaks pencarian issue GitHub
    "repos": ["owner/repo"],             # opsional: batasi ke repo tertentu
    "max_items": 100,
    "include_comments": true,
    "max_comments_per_item": 20,
}
"""

import time
from collections.abc import Iterator
from datetime import datetime

import httpx

from core.config import get_settings
from workers.adapters.base import BaseAdapter, RawItem

API = "https://api.github.com"


class GitHubAdapter(BaseAdapter):
    platform = "github"
    tier = "free"
    requires_credentials = True
    required_config = ()  # token boleh dari env
    rate_note = "5.000 req/jam dengan token; endpoint search dibatasi 30 req/menit."
    legal_note = "Konten repositori publik via API resmi."

    def collect(self, query: dict) -> Iterator[RawItem]:
        token = self.config.get("token") or get_settings().github_token
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ZandarOSINT/0.1",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        q = query.get("search", "")
        for repo in query.get("repos", []):
            q += f" repo:{repo}"
        if not q.strip():
            return

        max_items = int(query.get("max_items", 300))
        include_comments = query.get("include_comments", False)
        max_comments = int(query.get("max_comments_per_item", 50))

        fetched = 0
        page = 1
        while fetched < max_items and page <= 10:  # search API: maks 1000 hasil
            try:
                resp = httpx.get(
                    f"{API}/search/issues",
                    params={"q": q, "per_page": min(100, max_items - fetched), "page": page},
                    headers=headers,
                    timeout=30,
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])
            except (httpx.HTTPError, ValueError):
                return
            if not items:
                return

            for item in items:
                body = (item.get("body") or "").strip()
                title = item.get("title", "")
                if item.get("id"):
                    yield RawItem(
                        platform=self.platform,
                        external_id=f"issue:{item['id']}",
                        author=(item.get("user") or {}).get("login", "unknown"),
                        content=f"{title}\n\n{body}".strip(),
                        url=item.get("html_url"),
                        published_at=_parse_ts(item.get("created_at")),
                        title=title,
                        raw=item,
                    )
                    fetched += 1

                if include_comments and item.get("comments"):
                    yield from self._comments(item, headers, max_comments)

            page += 1
            time.sleep(2.5)  # jaga jauh di bawah 30 req/menit

    def _comments(self, item: dict, headers: dict, limit: int) -> Iterator[RawItem]:
        url = item.get("comments_url")
        if not url:
            return
        try:
            resp = httpx.get(url, params={"per_page": min(100, limit)}, headers=headers, timeout=30)
            resp.raise_for_status()
            comments = resp.json()
        except (httpx.HTTPError, ValueError):
            return
        finally:
            time.sleep(1)

        for c in comments[:limit]:
            body = (c.get("body") or "").strip()
            if not body or not c.get("id"):
                continue
            yield RawItem(
                platform=self.platform,
                external_id=f"comment:{c['id']}",
                author=(c.get("user") or {}).get("login", "unknown"),
                content=body,
                url=c.get("html_url"),
                published_at=_parse_ts(c.get("created_at")),
                title=item.get("title"),
                raw=c,
            )


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

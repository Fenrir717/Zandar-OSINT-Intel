"""Adapter X (Twitter) — API v2 recent search. SUMBER BERBAYAR (metered).

Perubahan penting Februari 2026: X meninggalkan tier langganan untuk pendaftar
baru dan pindah ke pay-per-use berbasis kredit — sekitar $0,005 per post yang
dibaca. Artinya X kini LAYAK untuk koleksi terarah bervolume kecil (10.000 post
≈ $50), bukan lagi tembok $5.000/bulan; tapi setiap panggilan menagih uang.

Karena itu adapter ini punya COST GUARD ganda:
  1. `confirm_metered_cost: true` wajib ada di query — mencegah job tak sengaja,
  2. `max_posts` wajib, dibatasi keras `MAX_POSTS_HARD_CAP`.

query = {
    "keywords": ["stimulus pangan"],
    "max_posts": 500,
    "confirm_metered_cost": true,
    "lang": "id",
}
"""

from collections.abc import Iterator
from datetime import datetime

import httpx

from core.config import get_settings
from workers.adapters.base import BaseAdapter, CostGuardRejected, RawItem

SEARCH = "https://api.x.com/2/tweets/search/recent"
MAX_POSTS_HARD_CAP = 5_000
USD_PER_POST_READ = 0.005  # tarif acuan 2026; verifikasi ulang sebelum run besar


class XAdapter(BaseAdapter):
    platform = "x"
    tier = "metered"
    requires_credentials = True
    required_config = ()  # bearer token boleh dari env
    rate_note = "Recent search: 7 hari terakhir, 100 post per halaman."
    cost_note = f"~${USD_PER_POST_READ}/post dibaca (pay-per-use 2026). Batas keras {MAX_POSTS_HARD_CAP} post/run."
    legal_note = "API resmi berbayar; tidak ada tier baca gratis sejak 2023."

    @staticmethod
    def estimate_cost_usd(max_posts: int) -> float:
        return round(max_posts * USD_PER_POST_READ, 2)

    def collect(self, query: dict) -> Iterator[RawItem]:
        if not query.get("confirm_metered_cost"):
            raise CostGuardRejected(
                "Adapter X berbayar per post. Set 'confirm_metered_cost': true pada query "
                f"setelah menyetujui estimasi (~${USD_PER_POST_READ}/post)."
            )
        max_posts = int(query.get("max_posts", 0))
        if max_posts <= 0 or max_posts > MAX_POSTS_HARD_CAP:
            raise CostGuardRejected(
                f"'max_posts' wajib diisi 1..{MAX_POSTS_HARD_CAP} (estimasi biaya: "
                f"${self.estimate_cost_usd(min(max(max_posts, 0), MAX_POSTS_HARD_CAP))})."
            )

        token = self.config.get("bearer_token") or get_settings().x_bearer_token
        self.config.setdefault("bearer_token", token)
        self.require_config("bearer_token")

        keywords = query.get("keywords", [])
        if not keywords:
            return
        q = " OR ".join(f'"{k}"' if " " in k else k for k in keywords)
        if query.get("lang"):
            q += f" lang:{query['lang']}"
        q += " -is:retweet"

        headers = {"Authorization": f"Bearer {token}", "User-Agent": "ZandarOSINT/0.1"}
        fetched = 0
        next_token: str | None = None

        while fetched < max_posts:
            params = {
                "query": q,
                "max_results": min(100, max_posts - fetched),
                "tweet.fields": "created_at,author_id,public_metrics,lang",
            }
            if next_token:
                params["next_token"] = next_token
            try:
                resp = httpx.get(SEARCH, params=params, headers=headers, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError):
                return

            for post in data.get("data", []):
                yield RawItem(
                    platform=self.platform,
                    external_id=post["id"],
                    author=post.get("author_id", "unknown"),
                    content=post.get("text", ""),
                    url=f"https://x.com/i/status/{post['id']}",
                    published_at=_parse_ts(post.get("created_at")),
                    raw=post,
                )
                fetched += 1

            next_token = data.get("meta", {}).get("next_token")
            if not next_token:
                return


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

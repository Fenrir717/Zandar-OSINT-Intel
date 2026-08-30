"""Adapter YouTube Data API v3 — commentThreads (1 unit/request; kuota 10rb/hari).

query = {
    "video_ids": ["abc123", ...],   # opsional bila 'keywords' diberi
    "keywords": ["bisnis laundry", ...],  # → cari video relevan lalu tarik komentar
    "max_videos": 10,               # opsional; batas video hasil pencarian keyword
    "max_per_video": 200,           # opsional
}
Butuh YOUTUBE_API_KEY di env. Bila video_ids kosong tapi ada keywords, adapter
mencari video (search.list, 100 unit/panggilan) → kumpulkan komentar. Dibatasi
`max_videos` agar hemat kuota (default 10 video ≈ 100 + 10 unit).
"""

from collections.abc import Iterator
from datetime import datetime

import httpx

from core.config import get_settings
from workers.adapters.base import BaseAdapter, RawItem

API = "https://www.googleapis.com/youtube/v3/commentThreads"
SEARCH_API = "https://www.googleapis.com/youtube/v3/search"


class YouTubeAdapter(BaseAdapter):
    platform = "youtube"
    tier = "free"
    requires_credentials = True
    rate_note = "Kuota 10.000 unit/hari; commentThreads 1 unit/permintaan."
    legal_note = "API resmi; hanya komentar publik."

    def collect(self, query: dict) -> Iterator[RawItem]:
        api_key = self.config.get("api_key") or get_settings().youtube_api_key
        if not api_key:
            raise RuntimeError("YOUTUBE_API_KEY belum diisi (env / sources.config)")

        max_per_video = int(query.get("max_per_video", 200))

        video_ids = list(query.get("video_ids", []))
        # Tanpa video_ids tapi ada keywords → cari video relevan (Indonesia) dulu.
        if not video_ids and query.get("keywords"):
            video_ids = self._search_videos(
                api_key, query["keywords"], int(query.get("max_videos", 10))
            )

        for video_id in video_ids:
            fetched = 0
            page_token: str | None = None
            while fetched < max_per_video:
                params = {
                    "part": "snippet",
                    "videoId": video_id,
                    "maxResults": min(100, max_per_video - fetched),
                    "textFormat": "plainText",
                    "key": api_key,
                }
                if page_token:
                    params["pageToken"] = page_token
                try:
                    resp = httpx.get(API, params=params, timeout=30)
                    resp.raise_for_status()
                except httpx.HTTPError:
                    break  # video dinonaktifkan komentarnya / kuota habis — lanjut video lain
                data = resp.json()

                for item in data.get("items", []):
                    top = item["snippet"]["topLevelComment"]["snippet"]
                    yield RawItem(
                        platform=self.platform,
                        external_id=item["id"],
                        author=top.get("authorChannelId", {}).get("value")
                        or top.get("authorDisplayName", "unknown"),
                        content=top.get("textDisplay", ""),
                        url=f"https://www.youtube.com/watch?v={video_id}&lc={item['id']}",
                        published_at=_parse_ts(top.get("publishedAt")),
                        raw=item,
                    )
                    fetched += 1

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

    def _search_videos(self, api_key: str, keywords: list[str], max_videos: int) -> list[str]:
        """search.list: keyword → daftar video_id relevan (bahasa/region Indonesia)."""
        q = " ".join(str(k) for k in keywords[:4])[:200]
        params = {
            "part": "snippet", "q": q, "type": "video",
            "maxResults": max(1, min(int(max_videos), 50)),
            "relevanceLanguage": "id", "regionCode": "ID",
            "order": "relevance", "key": api_key,
        }
        try:
            resp = httpx.get(SEARCH_API, params=params, timeout=30)
            resp.raise_for_status()
        except httpx.HTTPError:
            return []
        return [
            it["id"]["videoId"]
            for it in resp.json().get("items", [])
            if it.get("id", {}).get("videoId")
        ]


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

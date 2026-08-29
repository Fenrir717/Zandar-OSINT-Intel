"""Adapter YouTube Data API v3 — commentThreads (1 unit/request; kuota 10rb/hari).

query = {
    "video_ids": ["abc123", ...],
    "max_per_video": 200,           # opsional
}
Butuh YOUTUBE_API_KEY di env. Pencarian video by keyword (100 unit/req) sengaja
tidak dipakai default — boros kuota; daftar video ditentukan planner/analis.
"""

from collections.abc import Iterator
from datetime import datetime

import httpx

from core.config import get_settings
from workers.adapters.base import BaseAdapter, RawItem

API = "https://www.googleapis.com/youtube/v3/commentThreads"


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

        for video_id in query.get("video_ids", []):
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


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

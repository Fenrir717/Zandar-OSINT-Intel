"""Registry adapter koleksi.

Kunci registry = METODE koleksi (bisa berbeda dari label data `platform`): satu
platform bisa punya beberapa metode. Mis. X: x (API resmi metered), x_vendor
(shadow API murah), nitter (front-end) — ketiganya data platform="x".

Tier akses (PRD §5 + revisi):
  free    — API resmi/terbuka/arsip publik/parse lokal, tanpa biaya per-item
  metered — resmi tapi dibayar per pemakaian (guard biaya)
  vendor  — via penyedia data pihak ketiga berkontrak

Adapter berbasis halaman web (news/blog/website/rss) berbagi web_extract; vendor
(tiktok/x_vendor) berbagi vendor_base.
"""

from workers.adapters.base import (
    AdapterNotConfigured,
    BaseAdapter,
    CostGuardRejected,
    RawItem,
)
from workers.adapters.blog import BlogAdapter
from workers.adapters.bps import BPSAdapter
from workers.adapters.forum import ForumAdapter
from workers.adapters.github import GitHubAdapter
from workers.adapters.har_import import HarImportAdapter
from workers.adapters.news import NewsAdapter
from workers.adapters.nitter import NitterAdapter
from workers.adapters.reddit import RedditAdapter
from workers.adapters.rss import RssAdapter
from workers.adapters.telegram import TelegramAdapter
from workers.adapters.tiktok import TikTokAdapter
from workers.adapters.wayback import WaybackAdapter
from workers.adapters.website import WebsiteAdapter
from workers.adapters.x_twitter import XAdapter
from workers.adapters.x_vendor import XVendorAdapter
from workers.adapters.youtube import YouTubeAdapter
from workers.adapters.youtube_transcript import YouTubeTranscriptAdapter

_CLASSES: list[type[BaseAdapter]] = [
    RssAdapter, NewsAdapter, BlogAdapter, WebsiteAdapter, ForumAdapter, GitHubAdapter,
    YouTubeAdapter, RedditAdapter, TelegramAdapter, XAdapter, TikTokAdapter,
    # metode koleksi tambahan (revisi 30 Agu 2026)
    XVendorAdapter, HarImportAdapter, YouTubeTranscriptAdapter, WaybackAdapter, NitterAdapter,
    BPSAdapter,  # ground truth resmi
]

ADAPTERS: dict[str, type[BaseAdapter]] = {cls.registry_key(): cls for cls in _CLASSES}
PLATFORMS = tuple(ADAPTERS)


def describe_all() -> list[dict]:
    """Metadata seluruh adapter — dipakai UI Sources dan Graph A `select_sources`."""
    return [cls.describe() for cls in _CLASSES]


__all__ = [
    "ADAPTERS",
    "PLATFORMS",
    "AdapterNotConfigured",
    "BaseAdapter",
    "CostGuardRejected",
    "RawItem",
    "describe_all",
]

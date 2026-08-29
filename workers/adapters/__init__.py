"""Registry adapter koleksi.

Sebelas platform, tiga tier akses (PRD §5 + revisi 30 Agu 2026):

  free    — API resmi/terbuka, tanpa biaya per-item
            rss · news · blog · website · forum · github · youtube · reddit · telegram
  metered — resmi tapi dibayar per pemakaian, wajib guard biaya
            x
  vendor  — tidak ada akses resmi; hanya lewat penyedia data berkontrak
            tiktok

Adapter berbasis halaman web (news/blog/website, dan fallback rss) berbagi satu
modul ekstraksi `web_extract` — mereka berbeda hanya pada cara MENEMUKAN URL.
"""

from workers.adapters.base import (
    AdapterNotConfigured,
    BaseAdapter,
    CostGuardRejected,
    RawItem,
)
from workers.adapters.blog import BlogAdapter
from workers.adapters.forum import ForumAdapter
from workers.adapters.github import GitHubAdapter
from workers.adapters.news import NewsAdapter
from workers.adapters.reddit import RedditAdapter
from workers.adapters.rss import RssAdapter
from workers.adapters.telegram import TelegramAdapter
from workers.adapters.tiktok import TikTokAdapter
from workers.adapters.website import WebsiteAdapter
from workers.adapters.x_twitter import XAdapter
from workers.adapters.youtube import YouTubeAdapter

ADAPTERS: dict[str, type[BaseAdapter]] = {
    "rss": RssAdapter,
    "news": NewsAdapter,
    "blog": BlogAdapter,
    "website": WebsiteAdapter,
    "forum": ForumAdapter,
    "github": GitHubAdapter,
    "youtube": YouTubeAdapter,
    "reddit": RedditAdapter,
    "telegram": TelegramAdapter,
    "x": XAdapter,
    "tiktok": TikTokAdapter,
}

PLATFORMS = tuple(ADAPTERS)


def describe_all() -> list[dict]:
    """Metadata seluruh adapter — dipakai UI Sources dan Graph A `select_sources`."""
    return [cls.describe() for cls in ADAPTERS.values()]


__all__ = [
    "ADAPTERS",
    "PLATFORMS",
    "AdapterNotConfigured",
    "BaseAdapter",
    "CostGuardRejected",
    "RawItem",
    "describe_all",
]

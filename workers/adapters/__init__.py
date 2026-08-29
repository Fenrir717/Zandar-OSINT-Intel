from workers.adapters.base import BaseAdapter, RawItem
from workers.adapters.reddit import RedditAdapter
from workers.adapters.rss import RssAdapter
from workers.adapters.telegram import TelegramAdapter
from workers.adapters.youtube import YouTubeAdapter

ADAPTERS: dict[str, type[BaseAdapter]] = {
    "rss": RssAdapter,
    "youtube": YouTubeAdapter,
    "reddit": RedditAdapter,
    "telegram": TelegramAdapter,
}

__all__ = ["ADAPTERS", "BaseAdapter", "RawItem"]

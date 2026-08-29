"""Uji parsing RSS tanpa network — httpx.get dipatch dengan fixture lokal."""

import httpx

from workers.adapters.rss import RssAdapter

FEED_XML = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Portal Berita</title>
  <item>
    <title>Pemerintah umumkan paket stimulus pangan</title>
    <link>https://portal.example/artikel/1</link>
    <guid>artikel-1</guid>
    <description>Paket stimulus senilai besar untuk pangan diumumkan hari ini.</description>
    <pubDate>Fri, 29 Aug 2026 10:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Skor liga sepak bola pekan ini</title>
    <link>https://portal.example/artikel/2</link>
    <guid>artikel-2</guid>
    <description>Hasil pertandingan semalam.</description>
  </item>
</channel></rss>"""


def test_rss_adapter_filters_by_keyword(monkeypatch) -> None:
    def fake_get(url, **kwargs):
        return httpx.Response(200, content=FEED_XML, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr("workers.adapters.rss.time.sleep", lambda s: None)

    items = list(
        RssAdapter().collect({"feeds": ["https://portal.example/rss"], "keywords": ["stimulus"]})
    )
    assert len(items) == 1
    item = items[0]
    assert item.external_id == "artikel-1"
    assert item.platform == "rss"
    assert "stimulus" in item.content.lower()
    assert item.published_at is not None


def test_rss_adapter_no_keywords_takes_all(monkeypatch) -> None:
    def fake_get(url, **kwargs):
        return httpx.Response(200, content=FEED_XML, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr("workers.adapters.rss.time.sleep", lambda s: None)

    items = list(RssAdapter().collect({"feeds": ["https://portal.example/rss"]}))
    assert len(items) == 2

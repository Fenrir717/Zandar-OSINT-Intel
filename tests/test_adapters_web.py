"""Adapter berbasis web & API — diuji dengan fixture, tanpa jaringan."""

import httpx

from workers.adapters.forum import ForumAdapter
from workers.adapters.github import GitHubAdapter
from workers.adapters.news import NewsAdapter
from workers.adapters.tiktok import TikTokAdapter
from workers.adapters.website import WebsiteAdapter

ARTICLE_HTML = """<html><head><title>Stimulus pangan diumumkan</title></head><body>
<nav>menu menu menu</nav>
<article><h1>Stimulus pangan diumumkan</h1>
<p>Pemerintah mengumumkan paket stimulus pangan pada hari Jumat. Program ini menyasar rumah
tangga berpendapatan rendah di seluruh provinsi dan akan berjalan hingga akhir tahun anggaran
berikutnya, menurut keterangan resmi kementerian yang diterima wartawan pagi tadi.</p>
<p>Anggaran disalurkan lewat rekening kas daerah dengan pengawasan inspektorat, dan penerima
manfaat diverifikasi ulang menggunakan basis data terpadu yang diperbarui setiap kuartal.</p>
</article><footer>hak cipta</footer></body></html>"""

GDELT_JSON = {
    "articles": [
        {
            "url": "https://portal.example/artikel/1",
            "title": "Stimulus pangan diumumkan",
            "seendate": "20260829T101500Z",
            "domain": "portal.example",
            "language": "Indonesian",
        }
    ]
}


def _patch_get(monkeypatch, handler) -> None:
    monkeypatch.setattr(httpx, "get", handler)


def test_news_adapter_titles_only_mode(monkeypatch) -> None:
    def fake_get(url, **kwargs):
        return httpx.Response(200, json=GDELT_JSON, request=httpx.Request("GET", url))

    _patch_get(monkeypatch, fake_get)
    items = list(NewsAdapter().collect({"keywords": ["stimulus"], "fetch_full_text": False}))

    assert len(items) == 1
    assert items[0].platform == "news"
    assert items[0].external_id == "https://portal.example/artikel/1"
    assert items[0].published_at is not None


def test_news_adapter_fetches_full_text(monkeypatch) -> None:
    def fake_get(url, **kwargs):
        req = httpx.Request("GET", url)
        if "gdeltproject" in url:
            return httpx.Response(200, json=GDELT_JSON, request=req)
        if url.endswith("/robots.txt"):
            return httpx.Response(200, text="User-agent: *\nAllow: /", request=req)
        return httpx.Response(
            200, text=ARTICLE_HTML, headers={"content-type": "text/html"}, request=req
        )

    _patch_get(monkeypatch, fake_get)
    monkeypatch.setattr("workers.adapters.web_extract.time.sleep", lambda s: None)

    items = list(NewsAdapter().collect({"keywords": ["stimulus"]}))
    assert len(items) == 1
    assert "rekening kas daerah" in items[0].content  # teks penuh, bukan judul saja


def test_website_adapter_reads_sitemap(monkeypatch) -> None:
    sitemap = """<?xml version="1.0"?><urlset>
      <url><loc>https://situs.example/a</loc></url>
      <url><loc>https://situs.example/b</loc></url>
    </urlset>"""

    def fake_get(url, **kwargs):
        req = httpx.Request("GET", url)
        if url.endswith("/robots.txt"):
            return httpx.Response(200, text="User-agent: *\nAllow: /", request=req)
        if "sitemap" in url:
            return httpx.Response(
                200, text=sitemap, headers={"content-type": "application/xml"}, request=req
            )
        return httpx.Response(
            200, text=ARTICLE_HTML, headers={"content-type": "text/html"}, request=req
        )

    _patch_get(monkeypatch, fake_get)
    monkeypatch.setattr("workers.adapters.web_extract.time.sleep", lambda s: None)

    items = list(
        WebsiteAdapter().collect({"sitemaps": ["https://situs.example/sitemap.xml"], "max_pages": 5})
    )
    assert len(items) == 2
    assert {i.url for i in items} == {"https://situs.example/a", "https://situs.example/b"}


def test_website_adapter_obeys_robots_disallow(monkeypatch) -> None:
    def fake_get(url, **kwargs):
        req = httpx.Request("GET", url)
        if url.endswith("/robots.txt"):
            return httpx.Response(200, text="User-agent: *\nDisallow: /", request=req)
        return httpx.Response(
            200, text=ARTICLE_HTML, headers={"content-type": "text/html"}, request=req
        )

    _patch_get(monkeypatch, fake_get)
    monkeypatch.setattr("workers.adapters.web_extract.time.sleep", lambda s: None)

    items = list(WebsiteAdapter().collect({"urls": ["https://blokir.example/a"]}))
    assert items == []


def test_forum_adapter_discourse(monkeypatch) -> None:
    search = {"topics": [{"id": 42}]}
    topic = {
        "title": "Diskusi stimulus",
        "post_stream": {
            "posts": [
                {
                    "id": 1001,
                    "post_number": 1,
                    "username": "warga_a",
                    "cooked": "<p>Menurut saya programnya <b>bagus</b></p>",
                    "created_at": "2026-08-20T03:00:00Z",
                },
                {
                    "id": 1002,
                    "post_number": 2,
                    "username": "warga_b",
                    "cooked": "<p>Distribusinya lambat di daerah saya</p>",
                    "created_at": "2026-08-20T04:00:00Z",
                },
            ]
        },
    }

    def fake_get(url, **kwargs):
        req = httpx.Request("GET", url)
        payload = search if "search.json" in url else topic
        return httpx.Response(200, json=payload, request=req)

    _patch_get(monkeypatch, fake_get)
    monkeypatch.setattr("workers.adapters.forum.time.sleep", lambda s: None)

    items = list(
        ForumAdapter().collect({"base_url": "https://forum.example", "keywords": ["stimulus"]})
    )
    assert len(items) == 2
    assert items[0].author == "warga_a"
    assert "bagus" in items[0].content and "<b>" not in items[0].content  # HTML dibersihkan


def test_github_adapter_issues_and_comments(monkeypatch) -> None:
    issues = {
        "items": [
            {
                "id": 555,
                "title": "Kerentanan pada modul autentikasi",
                "body": "Detail laporan",
                "html_url": "https://github.com/o/r/issues/1",
                "created_at": "2026-08-01T00:00:00Z",
                "user": {"login": "peneliti"},
                "comments": 1,
                "comments_url": "https://api.github.com/repos/o/r/issues/1/comments",
            }
        ]
    }
    comments = [
        {
            "id": 777,
            "body": "Sudah kami tambal di rilis berikutnya",
            "html_url": "https://github.com/o/r/issues/1#c777",
            "created_at": "2026-08-02T00:00:00Z",
            "user": {"login": "maintainer"},
        }
    ]

    calls = {"n": 0}

    def fake_get(url, **kwargs):
        req = httpx.Request("GET", url)
        if "search/issues" in url:
            calls["n"] += 1
            return httpx.Response(200, json=issues if calls["n"] == 1 else {"items": []}, request=req)
        return httpx.Response(200, json=comments, request=req)

    _patch_get(monkeypatch, fake_get)
    monkeypatch.setattr("workers.adapters.github.time.sleep", lambda s: None)

    items = list(
        GitHubAdapter({"token": "x"}).collect(
            {"search": "kerentanan", "max_items": 1, "include_comments": True}
        )
    )
    assert [i.external_id for i in items] == ["issue:555", "comment:777"]
    assert items[1].author == "maintainer"


def test_tiktok_vendor_field_mapping(monkeypatch) -> None:
    payload = {
        "data": {
            "comments": [
                {"cid": "c1", "text": "setuju banget", "user": {"unique_id": "akun_a"},
                 "create_time": 1756500000, "share_url": "https://tiktok.example/c1"}
            ]
        }
    }

    def fake_get(url, **kwargs):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    _patch_get(monkeypatch, fake_get)

    adapter = TikTokAdapter(
        {
            "base_url": "https://api.vendor.example/comments",
            "api_key": "kunci",
            "items_path": "data.comments",
            "field_map": {
                "external_id": "cid",
                "author": "user.unique_id",
                "content": "text",
                "url": "share_url",
                "published_at": "create_time",
            },
        }
    )
    items = list(adapter.collect({"video_id": "123"}))
    assert len(items) == 1
    assert items[0].external_id == "c1"
    assert items[0].author == "akun_a"  # jalur bersarang terbaca
    assert items[0].published_at is not None

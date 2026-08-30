"""Adapter metode-koleksi baru: HAR-import, X-vendor, Wayback, Nitter."""

import json

import httpx
import pytest

from workers.adapters.base import AdapterNotConfigured
from workers.adapters.har_import import HarImportAdapter
from workers.adapters.nitter import NitterAdapter
from workers.adapters.wayback import WaybackAdapter
from workers.adapters.x_vendor import XVendorAdapter


def _write_har(tmp_path, bodies: list[dict]) -> str:
    entries = [
        {"response": {"content": {"mimeType": "application/json", "text": json.dumps(b)}}}
        for b in bodies
    ]
    p = tmp_path / "capture.har"
    p.write_text(json.dumps({"log": {"entries": entries}}), encoding="utf-8")
    return str(p)


def test_har_extracts_nested_posts(tmp_path) -> None:
    # Mensimulasikan respons GraphQL Threads/X: post bersarang dengan text+id
    body = {"data": {"feed": {"items": [
        {"post": {"pk": "111", "text": "harga BBM naik lagi", "username": "warga_a"}},
        {"post": {"pk": "222", "text": "stimulus cair alhamdulillah", "username": "warga_b"}},
    ]}}}
    har = _write_har(tmp_path, [body])
    items = list(HarImportAdapter().collect({"har_path": har, "platform": "threads"}))
    ids = {i.external_id for i in items}
    assert "threads:111" in ids and "threads:222" in ids
    assert all(i.platform == "threads" for i in items)
    a = next(i for i in items if i.external_id == "threads:111")
    assert a.author == "warga_a" and "BBM" in a.content


def test_har_keyword_filter(tmp_path) -> None:
    body = {"items": [
        {"id": "1", "text": "soal stimulus pangan"},
        {"id": "2", "text": "berita olahraga"},
    ]}
    har = _write_har(tmp_path, [body])
    items = list(HarImportAdapter().collect({"har_path": har, "platform": "x", "keywords": ["stimulus"]}))
    assert len(items) == 1 and items[0].external_id == "x:1"


def test_har_missing_path_raises() -> None:
    with pytest.raises(AdapterNotConfigured):
        list(HarImportAdapter().collect({"platform": "x"}))


def test_x_vendor_field_mapping(monkeypatch) -> None:
    payload = {"tweets": [
        {"id": "t1", "full_text": "ekonomi melambat", "user": {"screen_name": "akun_x"},
         "created_at": "2026-08-20T00:00:00Z", "url": "https://x.com/i/status/t1"},
    ]}

    def fake_get(url, **kw):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    adapter = XVendorAdapter({
        "base_url": "https://api.vendor.example/search", "api_key": "k",
        "items_path": "tweets",
        "field_map": {"external_id": "id", "author": "user.screen_name", "content": "full_text",
                      "url": "url", "published_at": "created_at"},
    })
    items = list(adapter.collect({"q": "ekonomi"}))
    assert len(items) == 1
    assert items[0].platform == "x"  # data dilabeli x meski via vendor
    assert items[0].external_id == "t1" and items[0].author == "akun_x"


def test_x_vendor_requires_config() -> None:
    with pytest.raises(AdapterNotConfigured):
        list(XVendorAdapter().collect({"q": "x"}))


def test_wayback_reads_cdx_and_extracts(monkeypatch) -> None:
    cdx = [["timestamp", "original", "statuscode", "mimetype"],
           ["20260815120000", "cnnindonesia.com/berita/1", "200", "text/html"]]
    para = "Isi artikel panjang. " * 20
    html = f"<html><head><title>Judul</title></head><body><article><p>{para}</p></article></body></html>"

    def fake_get(url, **kw):
        req = httpx.Request("GET", url)
        if "cdx" in url:
            return httpx.Response(200, json=cdx, request=req)
        return httpx.Response(200, text=html, headers={"content-type": "text/html"}, request=req)

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr("workers.adapters.web_extract.time.sleep", lambda s: None)
    items = list(WaybackAdapter().collect({"url": "cnnindonesia.com/*", "limit": 5}))
    assert len(items) == 1
    assert items[0].platform == "wayback"
    assert "Isi artikel" in items[0].content


def test_nitter_requires_base_url() -> None:
    with pytest.raises(AdapterNotConfigured):
        list(NitterAdapter().collect({"search": "stimulus"}))

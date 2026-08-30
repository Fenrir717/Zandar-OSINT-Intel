"""Adapter ground-truth: BMKG (gempa) & CKAN (Satu Data), via fixture."""

import httpx

from workers.adapters.bmkg import BMKGAdapter
from workers.adapters.ckan import CkanAdapter


def test_bmkg_parses_and_filters_magnitude(monkeypatch) -> None:
    payload = {"Infogempa": {"gempa": [
        {"Tanggal": "30 Agu 2026", "Jam": "09:54 WIB", "DateTime": "2026-08-30T02:54:08+00:00",
         "Magnitude": "5.1", "Kedalaman": "10 km", "Wilayah": "Laut Banda", "Potensi": "Tidak berpotensi tsunami"},
        {"Tanggal": "29 Agu 2026", "Jam": "08:00 WIB", "DateTime": "2026-08-29T01:00:00+00:00",
         "Magnitude": "3.2", "Kedalaman": "5 km", "Wilayah": "Jawa Barat"},
    ]}}

    def fake_get(url, **kw):
        assert "gempaterkini" in url
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    items = list(BMKGAdapter().collect({"feed": "gempaterkini", "min_magnitude": 4.0}))
    assert len(items) == 1  # 3.2 tersaring
    it = items[0]
    assert it.platform == "bmkg" and it.author == "BMKG"
    assert "Magnitudo 5.1" in it.content and "Laut Banda" in it.content
    assert it.published_at is not None


def test_bmkg_handles_single_dict(monkeypatch) -> None:
    payload = {"Infogempa": {"gempa": {
        "Tanggal": "30 Agu 2026", "Jam": "09:54 WIB", "DateTime": "2026-08-30T02:54:08+00:00",
        "Magnitude": "6.0", "Kedalaman": "20 km", "Wilayah": "Aceh"}}}

    def fake_get(url, **kw):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    items = list(BMKGAdapter().collect({"feed": "autogempa"}))
    assert len(items) == 1 and "Aceh" in items[0].content


def test_ckan_parses_datasets(monkeypatch) -> None:
    payload = {"success": True, "result": {"results": [
        {"name": "data-kemiskinan-2026", "title": "Data Kemiskinan 2026",
         "notes": "Persentase penduduk miskin per provinsi.",
         "organization": {"title": "BPS"}},
        {"name": "no-title", "notes": "x"},  # tanpa title -> dilewati
    ]}}

    def fake_get(url, **kw):
        assert "package_search" in url
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    items = list(CkanAdapter().collect({"base_url": "https://data.jakarta.go.id", "search": "kemiskinan"}))
    assert len(items) == 1
    it = items[0]
    assert it.platform == "satudata" and it.author == "BPS"
    assert "Kemiskinan" in it.content
    assert it.url.endswith("/dataset/data-kemiskinan-2026")

"""Adapter BPS — parsing respons WebAPI + guard token, via fixture (tanpa network)."""

import httpx
import pytest

from workers.adapters.base import AdapterNotConfigured
from workers.adapters.bps import BPSAdapter, _items


def test_bps_requires_token(monkeypatch) -> None:
    # Isolasi dari .env (mesin dev bisa punya BPS_TOKEN terisi)
    from core.config import get_settings

    monkeypatch.setenv("BPS_TOKEN", "")
    get_settings.cache_clear()
    with pytest.raises(AdapterNotConfigured):
        list(BPSAdapter().collect({"domain": "0000"}))
    get_settings.cache_clear()


def test_items_unwraps_meta_wrapper() -> None:
    # BPS membungkus sbg [meta, [items]]
    assert _items([{"page": 1}, [{"brs_id": 1}, {"brs_id": 2}]]) == [{"brs_id": 1}, {"brs_id": 2}]
    # atau langsung list item
    assert _items([{"brs_id": 3}]) == [{"brs_id": 3}]
    assert _items(None) == []


def test_bps_parses_pressrelease(monkeypatch) -> None:
    payload = {
        "status": "OK",
        "data": [
            {"page": 1, "pages": 1},
            [
                {"brs_id": "101", "title": "Inflasi Juli 2026 sebesar 2,1 persen",
                 "abstract": "BPS mencatat inflasi tahunan 2,1%.", "rl_date": "2026-08-01 08:00:00",
                 "pdf": "https://bps.go.id/brs/101.pdf"},
                {"brs_id": "102", "title": "Ekspor naik", "abstract": "Nilai ekspor meningkat."},
            ],
        ],
    }

    def fake_get(url, **kw):
        assert "pressrelease" in url and "key/tok123" in url
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    items = list(BPSAdapter({"token": "tok123"}).collect({"keywords": ["inflasi"]}))
    assert len(items) == 1  # hanya yang cocok keyword 'inflasi'
    it = items[0]
    assert it.external_id == "bps:101"
    assert it.platform == "bps"
    assert it.author == "Badan Pusat Statistik"
    assert "2,1 persen" in it.content
    assert it.published_at is not None

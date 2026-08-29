"""Registry adapter: kelengkapan, metadata, dan cost guard."""

import pytest

from workers.adapters import ADAPTERS, PLATFORMS, CostGuardRejected, describe_all
from workers.adapters.base import BaseAdapter
from workers.adapters.tiktok import TikTokAdapter
from workers.adapters.x_twitter import XAdapter

EXPECTED = {
    "rss", "news", "blog", "website", "forum",
    "github", "youtube", "reddit", "telegram", "x", "tiktok",
}


def test_registry_covers_all_eleven_platforms() -> None:
    assert set(PLATFORMS) == EXPECTED


def test_registry_keys_match_adapter_platform_attribute() -> None:
    for key, cls in ADAPTERS.items():
        assert cls.platform == key, f"{cls.__name__}.platform != kunci registry '{key}'"
        assert issubclass(cls, BaseAdapter)


def test_describe_all_reports_tiers() -> None:
    described = {d["platform"]: d for d in describe_all()}
    assert described["x"]["tier"] == "metered"
    assert described["tiktok"]["tier"] == "vendor"
    assert described["news"]["tier"] == "free"
    # Setiap sumber non-free wajib menjelaskan biayanya
    for meta in described.values():
        if meta["tier"] != "free":
            assert meta["cost_note"], f"{meta['platform']} tier {meta['tier']} tanpa cost_note"


def test_x_adapter_refuses_without_cost_confirmation() -> None:
    with pytest.raises(CostGuardRejected):
        list(XAdapter().collect({"keywords": ["tes"], "max_posts": 100}))


def test_x_adapter_refuses_unbounded_max_posts() -> None:
    with pytest.raises(CostGuardRejected):
        list(XAdapter().collect({"keywords": ["tes"], "confirm_metered_cost": True}))
    with pytest.raises(CostGuardRejected):
        list(
            XAdapter().collect(
                {"keywords": ["tes"], "confirm_metered_cost": True, "max_posts": 10_000_000}
            )
        )


def test_x_cost_estimate() -> None:
    assert XAdapter.estimate_cost_usd(1000) == 5.0


def test_tiktok_requires_vendor_config() -> None:
    from workers.adapters.base import AdapterNotConfigured

    with pytest.raises(AdapterNotConfigured):
        list(TikTokAdapter().collect({"video_id": "123"}))

"""Uji rantai fallback OpenAICompatProvider — tanpa jaringan (httpx dimock)."""

import json
import time

import httpx
import pytest

from core.config import get_settings
from graphs import llm as L


class _Resp:
    def __init__(self, status: int, payload: dict | None = None) -> None:
        self.status_code = status
        self._p = payload or {}
        self.text = "err-body"

    def json(self) -> dict:
        return self._p


def _ok(label: str) -> dict:
    return {
        "choices": [{"message": {"content": json.dumps({"label": label})}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2},
    }


@pytest.fixture
def _openrouter(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(time, "sleep", lambda *a: None)  # jangan benar-benar menunggu backoff
    get_settings.cache_clear()
    L.reset_llm()
    yield
    get_settings.cache_clear()
    L.reset_llm()


def test_parse_models() -> None:
    assert L._parse_models("a, b ,c") == ["a", "b", "c"]
    assert L._parse_models("solo") == ["solo"]


def test_fallback_on_bad_model(monkeypatch, _openrouter) -> None:
    """400 (slug salah) di model pertama → langsung coba model kedua (tanpa retry)."""
    monkeypatch.setenv("LLM_MODEL_F", "bad-slug,good-model")
    get_settings.cache_clear()
    L.reset_llm()
    seen: list[str] = []

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.append(json["model"])
        return _Resp(400) if json["model"] == "bad-slug" else _Resp(200, _ok("dari-kedua"))

    monkeypatch.setattr(httpx, "post", fake_post)
    r = L.get_llm().call_json("F", "s", "u")
    assert r.data["label"] == "dari-kedua"
    assert seen == ["bad-slug", "good-model"]  # 400 tak diretry


def test_retry_then_fallback_on_429(monkeypatch, _openrouter) -> None:
    """429 diretry 3x pada model pertama, lalu jatuh ke model kedua."""
    monkeypatch.setenv("LLM_MODEL_F", "m-a,m-b")
    get_settings.cache_clear()
    L.reset_llm()
    seen: list[str] = []

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.append(json["model"])
        return _Resp(429) if json["model"] == "m-a" else _Resp(200, _ok("b-menang"))

    monkeypatch.setattr(httpx, "post", fake_post)
    r = L.get_llm().call_json("F", "s", "u")
    assert r.data["label"] == "b-menang"
    assert seen == ["m-a", "m-a", "m-a", "m-b"]  # 3 percobaan m-a → m-b


def test_all_models_fail_raises(monkeypatch, _openrouter) -> None:
    monkeypatch.setenv("LLM_MODEL_F", "only-one")
    get_settings.cache_clear()
    L.reset_llm()
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(400))
    with pytest.raises(RuntimeError, match="Semua model LLM gagal"):
        L.get_llm().call_json("F", "s", "u")

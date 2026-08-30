"""Uji layer LLM: preset OpenAI-compatible + stub. Tanpa panggilan jaringan nyata."""

import httpx
import pytest

from graphs.llm import PRESETS, OpenAICompatProvider, StubProvider, _extract_json


def test_presets_have_four_backends() -> None:
    assert set(PRESETS) == {"groq", "gemini", "cerebras", "openrouter"}
    for base, env_key, mr, mf in PRESETS.values():
        assert base.startswith("https://")
        assert env_key.endswith("_api_key")
        assert mr and mf


def test_extract_json_tolerant() -> None:
    assert _extract_json('{"a": 1}') == {"a": 1}
    assert _extract_json('teks... {"a": 2} ...ekor') == {"a": 2}  # JSON di tengah
    assert _extract_json("bukan json") == {}


def test_provider_refuses_without_key(monkeypatch) -> None:
    # pastikan env key kosong
    from core.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("GROQ_API_KEY", "")
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        OpenAICompatProvider("groq")
    get_settings.cache_clear()


def test_openai_compat_call(monkeypatch) -> None:
    from core.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["model"] = json["model"]
        captured["temperature"] = json["temperature"]
        body = {
            "choices": [{"message": {"content": '{"topic": "harga bbm", "keywords_seed": ["bbm"]}'}}],
            "usage": {"prompt_tokens": 42, "completion_tokens": 12},
        }
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    p = OpenAICompatProvider("groq")
    r = p.call_json("R", "sistem", "query")
    assert r.data["topic"] == "harga bbm"
    assert r.tokens_in == 42 and r.tokens_out == 12
    assert captured["temperature"] == 0
    assert "groq.com" in captured["url"]
    assert captured["model"] == "openai/gpt-oss-120b"  # default Tier R groq (2026)
    get_settings.cache_clear()


def test_stub_still_default_no_key_needed() -> None:
    p = StubProvider()
    r = p.call_json("R", "s", "u", hint={"node": "parse_intent", "query": "isu ekonomi"})
    assert "topic" in r.data

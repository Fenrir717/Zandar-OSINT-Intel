"""Isolasi test dari .env mesin dev.

Tanpa ini, test yang mengandaikan provider/kredensial tertentu (stub, token kosong)
akan rusak saat developer mengisi .env nyata (groq, BPS_TOKEN, dst). Fixture autouse
memaksa nilai deterministik: provider stub/lexicon + kredensial kosong. Test yang
butuh nilai lain (mis. GROQ_API_KEY palsu) meng-override setelah fixture ini jalan.
"""

import pytest

# Kredensial/provider yang di-netralkan agar test tak bergantung .env
_NEUTRAL = {
    "LLM_PROVIDER": "stub",
    "LLM_MODEL_R": "",  # override .env → test pakai default preset
    "LLM_MODEL_F": "",
    "CLASSIFIER_PROVIDER": "lexicon",
    "GROQ_API_KEY": "",
    "GEMINI_API_KEY": "",
    "CEREBRAS_API_KEY": "",
    "OPENROUTER_API_KEY": "",
    "ANTHROPIC_API_KEY": "",
    "BPS_TOKEN": "",
    "YOUTUBE_API_KEY": "",
    "GITHUB_TOKEN": "",
    "X_BEARER_TOKEN": "",
}


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    from core.config import get_settings

    # setenv "" meng-override nilai dari file .env (env var menang atas .env)
    for key, val in _NEUTRAL.items():
        monkeypatch.setenv(key, val)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

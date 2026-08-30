"""Layer LLM ber-tier untuk node LangGraph (PRD §7.4).

Dua tier abstrak, ditukar via env — kode graph tak pernah menyebut vendor:
  Tier R (reasoning): parse_intent, select_sources, risk_scoring, ...
  Tier F (flash)    : expand_keywords, label_narrative, ...

Provider 'stub' (default) mengembalikan output terstruktur deterministik TANPA API
key, sehingga graph berjalan end-to-end sekarang. Provider 'openrouter'/'anthropic'
menyusul; kontraknya sama (call_json). Semua panggilan melaporkan token untuk
pencatatan agent_runs + budget cap.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

from core.config import get_settings

Tier = Literal["R", "F"]


@dataclass
class LLMResult:
    data: dict
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class Usage:
    """Akumulasi token/biaya per run graph — ditulis ke agent_runs."""

    tokens_in: int = 0
    tokens_out: int = 0
    calls: int = 0

    def add(self, r: LLMResult) -> None:
        self.tokens_in += r.tokens_in
        self.tokens_out += r.tokens_out
        self.calls += 1


class LLMProvider:
    def call_json(self, tier: Tier, system: str, user: str, hint: dict | None = None) -> LLMResult:
        raise NotImplementedError


# ---------------------------------------------------------------- stub

_STOP = {
    "yang", "dan", "di", "ke", "dari", "untuk", "pada", "dengan", "atau", "ini", "itu",
    "adalah", "akan", "sudah", "juga", "saya", "kita", "mereka", "tentang", "para",
    "the", "a", "an", "of", "to", "in", "for", "and", "or", "is", "are",
}
_WORD = re.compile(r"[a-zA-Z][a-zA-Z0-9-]+")


class StubProvider(LLMProvider):
    """Heuristik deterministik menyerupai output LLM — cukup realistis untuk
    menguji topologi graph, interrupt/resume, dan dispatch tanpa API key."""

    def call_json(self, tier: Tier, system: str, user: str, hint: dict | None = None) -> LLMResult:
        hint = hint or {}
        kind = hint.get("node", "")
        text = hint.get("query", user)
        toks_in = len((system + user).split())

        if kind == "parse_intent":
            words = [w.lower() for w in _WORD.findall(text) if w.lower() not in _STOP]
            data = {
                "topic": " ".join(words[:4]) or text[:40],
                "actors": [],
                "region": "ID",
                "period_days": hint.get("period_days", 30),
                "languages": ["id"],
                "keywords_seed": words[:6],
            }
        elif kind == "expand_keywords":
            seed: list[str] = hint.get("keywords_seed", [])
            expanded: list[str] = []
            for k in seed:
                expanded.append(k)
                if not k.startswith("#"):
                    expanded.append("#" + k.replace(" ", ""))
            data = {"keywords": list(dict.fromkeys(expanded))[:12]}
        elif kind == "select_sources":
            # Stub memilih sumber free-tier tanpa kredensial (aman untuk dijalankan)
            kws: list[str] = hint.get("keywords", [])
            news_q = {"keywords": kws[:4], "timespan": "7d", "fetch_full_text": False}
            data = {
                "sources": [
                    {"platform": "news", "query": news_q, "est_items": 200},
                    {"platform": "rss", "query": {"feeds": [], "keywords": kws[:4]}, "est_items": 100},
                ]
            }
        else:
            data = {}
        return LLMResult(data=data, tokens_in=toks_in, tokens_out=len(json.dumps(data).split()))


# ---------------------------------------------------------------- OpenAI-compatible

# Preset backend gratis/murah (semua endpoint OpenAI-compatible). Model default per
# tier bisa ditimpa via LLM_MODEL_R / LLM_MODEL_F di env.
#   name -> (base_url, env_key, default_model_R, default_model_F)
PRESETS: dict[str, tuple[str, str, str, str]] = {
    "groq": (
        "https://api.groq.com/openai/v1", "groq_api_key",
        "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
    ),
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai", "gemini_api_key",
        "gemini-2.5-flash", "gemini-2.5-flash-lite",
    ),
    "cerebras": (
        "https://api.cerebras.ai/v1", "cerebras_api_key",
        "llama-3.3-70b", "llama3.1-8b",
    ),
    "openrouter": (
        "https://openrouter.ai/api/v1", "openrouter_api_key",
        "z-ai/glm-4.6", "z-ai/glm-4.5-air",
    ),
}


class OpenAICompatProvider(LLMProvider):
    """Satu provider untuk semua backend OpenAI-compatible (Groq/Gemini/Cerebras/
    OpenRouter). Dipilih via LLM_PROVIDER; kunci dari env sesuai preset. temperature 0
    + JSON mode. Melaporkan token untuk agent_runs + budget cap."""

    def __init__(self, preset: str) -> None:
        base_url, env_key, default_r, default_f = PRESETS[preset]
        self.preset = preset
        self.base_url = base_url
        s = get_settings()
        self.key = getattr(s, env_key, "")
        if not self.key:
            raise RuntimeError(
                f"LLM_PROVIDER={preset} tapi {env_key.upper()} kosong. Daftar di provider, "
                f"lalu isi {env_key.upper()} di .env."
            )
        self.model_r = s.llm_model_r or default_r
        self.model_f = s.llm_model_f or default_f

    def call_json(self, tier: Tier, system: str, user: str, hint: dict | None = None) -> LLMResult:
        import httpx

        model = self.model_r if tier == "R" else self.model_f
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.key}"},
            json={
                "model": model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system + "\nBalas HANYA JSON valid, tanpa teks lain."},
                    {"role": "user", "content": user},
                ],
            },
            timeout=60,
        )
        resp.raise_for_status()
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        return LLMResult(
            data=_extract_json(content),
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
        )


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        m = re.search(r"\{.*\}", text or "", re.DOTALL)
        return json.loads(m.group(0)) if m else {}


_instance: LLMProvider | None = None


def get_llm() -> LLMProvider:
    global _instance
    if _instance is None:
        name = get_settings().llm_provider
        if name == "stub":
            _instance = StubProvider()
        elif name in PRESETS:
            _instance = OpenAICompatProvider(name)
        else:
            raise ValueError(f"LLM_PROVIDER tidak dikenal: {name} (pilih: stub, {', '.join(PRESETS)})")
    return _instance


# dipakai node & test untuk reset singleton bila config berubah
def reset_llm() -> None:
    global _instance
    _instance = None


__all__ = ["LLMProvider", "LLMResult", "Tier", "Usage", "get_llm", "reset_llm"]

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    zandar_env: str = "dev"

    jwt_secret: str = "dev-only-ganti-di-env"
    jwt_access_ttl_minutes: int = 60
    jwt_refresh_ttl_days: int = 7

    database_url: str = "postgresql+asyncpg://zandar:zandar@localhost:5432/zandar"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "zandarneo4j"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "zandar"
    minio_secret_key: str = "zandarminio"
    minio_bucket_raw: str = "raw"

    # Pseudonimisasi author (UU PDP) — WAJIB diganti di produksi
    author_hash_salt: str = "dev-only-ganti-salt"

    # Kredensial sumber (Fase 1)
    youtube_api_key: str = ""
    github_token: str = ""
    x_bearer_token: str = ""  # sumber metered — lihat XAdapter cost guard
    bps_token: str = ""  # BPS WebAPI (ground truth) — daftar di webapi.bps.go.id/developer

    anthropic_api_key: str = ""
    openrouter_api_key: str = ""

    # Klasifikasi (Fase 2) — lexicon (default, tanpa GPU) | indobert (multi-model) | flash
    classifier_provider: str = "lexicon"
    indobert_sentiment_model: str = "w11wo/indonesian-roberta-base-sentiment-classifier"
    # Emosi: default dilatih EmoT/Twitter (cocok domain medsos, ~F1 0.72).
    # Alternatif review-produk: w11wo/indonesian-roberta-base-prdect-id (F1 ~0.42 di tweet).
    indobert_emotion_model: str = "StevenLimcorn/indonesian-roberta-base-emotion-classifier"
    indobert_hatespeech_model: str = "Hate-speech-CNERG/dehatebert-mono-indonesian"

    # Orkestrasi LangGraph (Fase 2) — stub (default) | groq | gemini | cerebras | openrouter
    llm_provider: str = "stub"
    llm_model_r: str = ""  # kosong = default preset per provider (Tier R reasoning)
    llm_model_f: str = ""  # kosong = default preset per provider (Tier F flash)

    # Kunci provider LLM gratis (isi salah satu sesuai LLM_PROVIDER)
    groq_api_key: str = ""
    gemini_api_key: str = ""
    cerebras_api_key: str = ""

    # Embedding (Fase 2) — stub (default, tanpa key) | gemini (gratis, token-based) | local
    embed_provider: str = "stub"
    embed_model: str = ""  # kosong = default per provider
    qdrant_collection: str = "comments_v1"

    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()

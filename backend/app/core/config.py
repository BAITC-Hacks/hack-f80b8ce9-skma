from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Hackathon API"
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:3000"]
    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/ekt"

    # ekt.kz partner API (Basic Auth)
    ekt_api_url: str = "https://ekt.kz/api"
    ekt_api_user: str = ""
    ekt_api_password: str = ""
    ekt_sync_pages: int = 0  # 0 = all pages
    ekt_site_url: str = "https://ekt.kz"
    catalog_path: str = "data/catalog.json"
    detail_cache_path: str = "data/details_cache.sqlite"
    detail_ttl_seconds: int = 600
    detail_timeout_seconds: float = 8
    analog_timeout_seconds: float = 4

    # Main LLM (dialog + tools). Any OpenAI-compatible API: OpenAI (default),
    # build.nvidia.com (Qwen), own NIM on Brev
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"
    openai_timeout_seconds: float = 30
    # For reasoning models (gpt-5*, o*): "minimal" / "low" keeps chat latency down.
    openai_reasoning_effort: str | None = None

    # Hybrid mode: Kazakh model (Sherkala-8B via vLLM on Brev) rewrites replies to Kazakh
    # questions. Empty base URL = off.
    kazakh_llm_base_url: str = ""
    kazakh_llm_api_key: str = "EMPTY"  # vLLM accepts any key unless started with --api-key
    kazakh_llm_model: str = "inception42/Llama-3.1-Sherkala-8B-Chat"
    kazakh_llm_timeout_seconds: float = 15


settings = Settings()

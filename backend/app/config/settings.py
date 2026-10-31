from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações de execução compartilhadas pelas camadas do backend.

    A API e as integrações externas podem usar estas configurações. O serviço
    de negócio usa o provedor simulado por padrão, para que o desenvolvimento
    local não exija credenciais externas.
    """

    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000,http://localhost:8080"

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"
    nutrition_provider: str = "mock"
    database_url: str | None = None
    analysis_prompt_version: str = "v0008"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

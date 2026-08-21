"""Application settings, loaded from the repo-root .env file.

Assumes the process is started with the repo root as the current working
directory (matching how uvicorn, pytest, and every tool in tools/ are run
in this project) so that the relative env_file path below resolves.
"""

from functools import lru_cache

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    anthropic_api_key: str
    anthropic_model: str = Field(default="claude-haiku-4-5")
    keycloak_url: str
    keycloak_customers_realm: str = Field(default="travel-customers")
    keycloak_customers_api_client: str = Field(default="orchestrator-api")
    log_level: str = Field(default="INFO")
    environment: str = Field(default="development")

    @property
    def keycloak_issuer(self) -> str:
        return f"{self.keycloak_url}/realms/{self.keycloak_customers_realm}"

    @property
    def keycloak_discovery_url(self) -> str:
        return (
            f"{self.keycloak_url}/realms/{self.keycloak_customers_realm}"
            "/.well-known/openid-configuration"
        )


@lru_cache
def get_settings() -> Settings:
    """Process-wide cached Settings singleton.

    Called from main.py's lifespan so the service fails fast, before
    accepting any traffic, if a required variable is missing -- and as a
    FastAPI dependency wherever a handler needs config.
    """
    try:
        return Settings()
    except ValidationError as exc:
        missing = [
            ".".join(str(part) for part in error["loc"]).upper()
            for error in exc.errors()
            if error["type"] == "missing"
        ]
        if missing:
            raise RuntimeError(
                "Missing required environment variable(s): "
                f"{', '.join(missing)}. Copy .env.example to .env at the "
                "repo root and fill in real values."
            ) from exc
        raise

"""Application configuration loaded from environment / .env.

All settings are read once and cached. Import the module-level ``settings``
object anywhere you need config.
"""
from functools import lru_cache
import json

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unrelated env vars (e.g. frontend VITE_*)
    )

    # App
    app_name: str = "QueueGames API"
    environment: str = "development"
    api_v1_prefix: str = "/api"

    # CORS — accepts a JSON array or a comma-separated string (see cors_origins_list)
    cors_origins: str = "http://localhost:5173"

    # Public URL of the customer-facing SPA (used to build QR codes / links)
    frontend_base_url: str = "http://localhost:5173"

    # Database — Supabase Postgres connection string (or any Postgres URL)
    database_url: str = ""

    # Supabase project
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""  # verifies staff/admin JWTs

    # Customer password-less session tokens (minted by this API).
    # No default: must be set explicitly (see security._customer_secret).
    customer_jwt_secret: str = ""
    customer_session_ttl_minutes: int = 120

    @property
    def cors_origins_list(self) -> list[str]:
        """Allowed CORS origins.

        Tolerates both a JSON array (e.g. '["https://a.com","https://b.com"]')
        and a plain comma-separated string, stripping stray brackets/quotes.
        """
        raw = self.cors_origins.strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except ValueError:
                parsed = None
            if isinstance(parsed, list):
                return [str(o).strip().rstrip("/") for o in parsed if str(o).strip()]
        return [
            cleaned.rstrip("/")
            for part in raw.strip("[]").split(",")
            if (cleaned := part.strip().strip('"').strip("'"))
        ]

    @property
    def supabase_base_url(self) -> str:
        """Bare project URL (no trailing slash, no ``/rest/v1`` suffix).

        Tolerates pasting the Data API URL (``https://<ref>.supabase.co/rest/v1``)
        into SUPABASE_URL — the Auth Admin API needs the project root.
        """
        url = self.supabase_url.strip().rstrip("/")
        if url.endswith("/rest/v1"):
            url = url[: -len("/rest/v1")]
        return url

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

"""Application configuration loaded from environment variables.

Flow: .env → Settings → settings (singleton used across the app)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings. Field names map to UPPER_SNAKE env vars automatically.

    Example: database_url ← DATABASE_URL in .env
    """

    # App metadata
    app_name: str
    app_env: str
    debug: bool

    # PostgreSQL connection string (postgresql+asyncpg://...)
    database_url: str

    # JWT signing and expiration
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


# Single settings instance — import this everywhere instead of reading .env directly
settings = Settings()

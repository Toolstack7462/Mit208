"""Application configuration, loaded from environment / .env file."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PostgreSQL is the OFFICIAL target (set DATABASE_URL in .env — see .env.example).
    # When DATABASE_URL is not provided at all, fall back to a zero-install SQLite
    # file so the app still runs instantly for quick local testing.
    database_url: str = "sqlite:///./phishguard.db"
    secret_key: str = "dev-only-change-me-please-0123456789abcdef"
    access_token_expire_minutes: int = 480
    algorithm: str = "HS256"
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

"""Application configuration, loaded from environment / .env file."""
import logging
import secrets

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# The placeholder shipped in .env.example. Treated as "no secret configured".
INSECURE_SECRET_PLACEHOLDER = "CHANGE_ME_GENERATE_A_RANDOM_64_CHAR_SECRET"

# Historical default that was previously hard-coded in this file. Still listed so
# an existing developer .env carrying that value is rejected rather than trusted.
_KNOWN_WEAK_SECRETS = {
    INSECURE_SECRET_PLACEHOLDER,
    "dev-only-change-me-please-0123456789abcdef",
    "changeme",
    "secret",
}

MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    # PostgreSQL is the OFFICIAL target (set DATABASE_URL in .env — see .env.example).
    # When DATABASE_URL is not provided at all, fall back to a zero-install SQLite
    # file so the app still runs instantly for quick local testing.
    database_url: str = "sqlite:///./phishguard.db"

    # "development" | "production". Controls how strictly SECRET_KEY is enforced
    # and whether internal error detail is returned to the client.
    environment: str = "development"

    # No usable default: a missing/weak secret is either replaced with a random
    # per-process value (development) or refused outright (production). See
    # _validate_secret below.
    secret_key: str = INSECURE_SECRET_PLACEHOLDER
    access_token_expire_minutes: int = 480
    algorithm: str = "HS256"
    frontend_origin: str = "http://localhost:5173"

    # Brute-force protection for /api/auth/login.
    login_max_attempts: int = 10
    login_window_seconds: int = 300

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in ("production", "prod")

    @model_validator(mode="after")
    def _validate_secret(self) -> "Settings":
        """Refuse to run production with a weak JWT signing key.

        A predictable signing key lets anyone forge an admin token, so it cannot
        simply be warned about and ignored. In development we substitute a random
        per-process secret (tokens stop working across restarts, which is the
        intended nudge to configure a real one); in production we fail fast.
        """
        weak = self.secret_key in _KNOWN_WEAK_SECRETS or len(self.secret_key) < MIN_SECRET_LENGTH
        if not weak:
            return self

        if self.is_production:
            raise ValueError(
                "SECRET_KEY is missing, too short, or still set to the example placeholder. "
                f"Set a random value of at least {MIN_SECRET_LENGTH} characters in backend/.env "
                "before running with ENVIRONMENT=production. Generate one with:\n"
                '  python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )

        # Development: keep the app runnable, but never with a guessable key.
        object.__setattr__(self, "secret_key", secrets.token_urlsafe(48))
        logger.warning(
            "SECRET_KEY is not configured; using a random development key. "
            "Issued tokens become invalid when the server restarts. "
            "Set SECRET_KEY in backend/.env to keep sessions stable."
        )
        return self


settings = Settings()

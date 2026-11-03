"""Settings come from environment variables (or the local .env file)."""
from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # hide_input_in_errors: a bad value (like a weak JWT_SECRET) is never printed in the error.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    environment: str = "development"
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    frontend_origin: str = "http://localhost:5173"
    cookie_secure: bool = False
    rate_limit_enabled: bool = True
    seed_user_password: str | None = None

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_must_be_strong(cls, value: str) -> str:
        # The error text never includes the value itself.
        if len(value) < 32 or value.startswith("change-me"):
            raise ValueError("JWT_SECRET must be a random value of 32+ characters")
        return value

    @model_validator(mode="after")
    def production_must_use_secure_cookies(self) -> "Settings":
        if self.environment == "production" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true when ENVIRONMENT=production")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

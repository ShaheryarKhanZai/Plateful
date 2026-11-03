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

    # Database connection pool, PER API INSTANCE. With several instances the total number of
    # connections is (db_pool_size + db_max_overflow) x instances, and PostgreSQL allows 100 by
    # default. cluster/run_cluster.py sets these for you based on how many instances you start.
    db_pool_size: int = 15
    db_max_overflow: int = 15
    db_pool_timeout: int = 10
    # Shown in the X-Instance response header so you can see which instance answered a request.
    instance_name: str = ""

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

import pytest
from pydantic import ValidationError

from app.config import Settings

DB = "postgresql+psycopg://u:p@localhost/db_test"


def test_weak_jwt_secret_is_rejected_without_printing_it():
    secret = "change-me-super-secret-value-that-must-not-leak"
    with pytest.raises(ValidationError) as exc:
        Settings(database_url=DB, jwt_secret=secret)
    assert secret not in str(exc.value)


def test_short_jwt_secret_is_rejected():
    with pytest.raises(ValidationError):
        Settings(database_url=DB, jwt_secret="too-short")


def test_production_requires_secure_cookies():
    good = "x" * 40
    with pytest.raises(ValidationError):
        Settings(database_url=DB, jwt_secret=good, environment="production", cookie_secure=False)
    assert Settings(database_url=DB, jwt_secret=good, environment="production", cookie_secure=True).is_production

"""Password hashing and tokens."""
import datetime as dt
import hashlib
import secrets
import uuid

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.config import get_settings
from app.errors import AppError

# argon2-cffi's PasswordHasher uses Argon2id with the RFC 9106 recommended defaults.
_hasher = PasswordHasher()
# Verifying against this when the email is unknown keeps login timing similar,
# so attackers cannot tell which emails exist.
DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    s = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": str(user_id), "typ": "access", "iat": now,
              "exp": now + dt.timedelta(minutes=s.access_token_minutes)}
    return jwt.encode(claims, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID:
    s = get_settings()
    try:
        # algorithms is pinned, so a forged "alg: none" token is rejected.
        claims = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm],
                            options={"require": ["exp", "iat", "sub"]})
        if claims.get("typ") != "access":
            raise jwt.InvalidTokenError("wrong type")
        return uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise AppError(401, "invalid_token", "Your session has expired. Please log in again.",
                       {"WWW-Authenticate": "Bearer"})


def new_refresh_token() -> tuple[str, str]:
    """Returns (raw_token_for_cookie, hash_for_database)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

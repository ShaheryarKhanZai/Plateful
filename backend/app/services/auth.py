"""Auth business rules: register, log in, rotate refresh tokens, log out."""
import datetime as dt

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.models import User
from app.repositories import users as repo
from app.schemas import LoginIn, ProfileUpdate, RegisterIn
from app.security import (
    DUMMY_HASH, create_access_token, hash_password, hash_refresh_token,
    new_refresh_token, verify_password,
)


def _issue_tokens(db: Session, user: User) -> tuple[str, str]:
    raw, token_hash = new_refresh_token()
    expires = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=get_settings().refresh_token_days)
    repo.add_refresh_token(db, user.id, token_hash, expires)
    return create_access_token(user.id), raw


def register(db: Session, data: RegisterIn) -> tuple[User, str, str]:
    # Public registration ALWAYS creates a customer. Staff are created by an admin script.
    user = User(email=data.email, full_name=data.full_name, role="customer",
                password_hash=hash_password(data.password))
    try:
        repo.add(db, user)
        access, refresh = _issue_tokens(db, user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "email_taken", "An account with this email already exists.")
    return user, access, refresh


def login(db: Session, data: LoginIn) -> tuple[User, str, str]:
    user = repo.get_by_email(db, data.email)
    # Always run one password check, even for unknown emails (see security.DUMMY_HASH).
    ok = verify_password(user.password_hash if user else DUMMY_HASH, data.password)
    if not user or not ok:
        raise AppError(401, "invalid_credentials", "Incorrect email or password.")
    access, refresh = _issue_tokens(db, user)
    db.commit()
    return user, access, refresh


def refresh(db: Session, raw_token: str) -> tuple[User, str, str]:
    """Rotation: every refresh token works once. Reusing an old one means it may have
    been stolen, so we revoke ALL of that user's sessions."""
    row = repo.get_refresh_token(db, hash_refresh_token(raw_token), for_update=True)
    if row is None:
        raise AppError(401, "invalid_refresh", "Please log in again.")
    now = dt.datetime.now(dt.timezone.utc)
    if row.revoked_at is not None:
        repo.revoke_all_refresh_tokens(db, row.user_id)
        db.commit()
        raise AppError(401, "invalid_refresh", "Please log in again.")
    if row.expires_at <= now:
        raise AppError(401, "invalid_refresh", "Please log in again.")
    row.revoked_at = now
    user = repo.get_by_id(db, row.user_id)
    assert user is not None  # guaranteed by the foreign key
    access, new_raw = _issue_tokens(db, user)
    db.commit()
    return user, access, new_raw


def logout(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    row = repo.get_refresh_token(db, hash_refresh_token(raw_token))
    if row and row.revoked_at is None:
        row.revoked_at = dt.datetime.now(dt.timezone.utc)
        db.commit()


def update_profile(db: Session, user: User, data: ProfileUpdate) -> User:
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.default_address is not None:
        user.default_address = data.default_address
    db.commit()
    return user

"""Data access for users and refresh tokens. Only this layer talks SQL.
All queries use SQLAlchemy expressions, so values are always sent as bound parameters."""
import datetime as dt
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import RefreshToken, User


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def add(db: Session, user: User) -> User:
    db.add(user)
    db.flush()  # raises IntegrityError right away if the email already exists
    return user


def add_refresh_token(db: Session, user_id: uuid.UUID, token_hash: str, expires_at: dt.datetime) -> None:
    db.add(RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at))
    db.flush()


def get_refresh_token(db: Session, token_hash: str, for_update: bool = False) -> RefreshToken | None:
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def revoke_all_refresh_tokens(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=dt.datetime.now(dt.timezone.utc)))

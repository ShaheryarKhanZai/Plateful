"""Reusable FastAPI dependencies: who is calling, and are they allowed?"""
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.errors import AppError
from app.models import User
from app.repositories import users as users_repo
from app.security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise AppError(401, "not_authenticated", "Please log in.", {"WWW-Authenticate": "Bearer"})
    user = users_repo.get_by_id(db, decode_access_token(creds.credentials))
    if user is None:
        raise AppError(401, "invalid_token", "Your session has expired. Please log in again.",
                       {"WWW-Authenticate": "Bearer"})
    return user  # role comes from the database, not from the token


def require_role(role: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise AppError(403, "forbidden", "You don't have access to this.")
        return user
    return dependency


require_customer = require_role("customer")
require_staff = require_role("staff")


def require_csrf_protection(request: Request) -> None:
    """For endpoints that rely on the refresh COOKIE (refresh, logout).

    1) A custom header: other websites can't add it without our CORS approval.
    2) If the browser sends an Origin header, it must be our frontend.
    The access token is sent in an Authorization header, so other endpoints don't need this."""
    if request.headers.get("x-requested-with") != "fetch":
        raise AppError(403, "csrf_rejected", "Request rejected.")
    origin = request.headers.get("origin")
    if origin is not None and origin != get_settings().frontend_origin:
        raise AppError(403, "csrf_rejected", "Request rejected.")

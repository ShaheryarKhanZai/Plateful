from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, require_csrf_protection
from app.errors import AppError
from app.limiter import login_email_limiter, login_limiter, refresh_limiter, register_limiter
from app.models import User
from app.schemas import AuthOut, LoginIn, ProfileUpdate, RegisterIn, UserOut
from app.services import auth as service

router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE = "refresh_token"


def _set_cookie(response: Response, raw: str) -> None:
    s = get_settings()
    response.set_cookie(
        COOKIE, raw, max_age=s.refresh_token_days * 86400,
        httponly=True,            # JavaScript can't read it (protects against XSS theft)
        secure=s.cookie_secure,   # true in production (HTTPS only)
        samesite="strict",        # not sent on requests started by other sites
        path="/auth")             # only sent to /auth/* endpoints


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/auth", httponly=True,
                           secure=get_settings().cookie_secure, samesite="strict")


def _auth_response(response: Response, user: User, access: str, refresh: str) -> AuthOut:
    _set_cookie(response, refresh)
    response.headers["Cache-Control"] = "no-store"
    return AuthOut(access_token=access, user=UserOut.model_validate(user))


@router.post("/register", response_model=AuthOut, status_code=201,
             dependencies=[Depends(register_limiter.by_ip("register"))])
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)):
    return _auth_response(response, *service.register(db, body))


@router.post("/login", response_model=AuthOut,
             dependencies=[Depends(login_limiter.by_ip("login"))])
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    login_email_limiter.check(f"login:{body.email}")  # also limit guessing against one account
    return _auth_response(response, *service.login(db, body))


@router.post("/refresh", response_model=AuthOut,
             dependencies=[Depends(refresh_limiter.by_ip("refresh")), Depends(require_csrf_protection)])
def refresh(response: Response, db: Session = Depends(get_db),
            refresh_token: str | None = Cookie(default=None)):
    if not refresh_token:
        raise AppError(401, "invalid_refresh", "Please log in again.")
    try:
        return _auth_response(response, *service.refresh(db, refresh_token))
    except AppError:
        _clear_cookie(response)
        raise


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf_protection)])
def logout(response: Response, db: Session = Depends(get_db),
           refresh_token: str | None = Cookie(default=None)):
    service.logout(db, refresh_token)
    _clear_cookie(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileUpdate, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    return service.update_profile(db, user, body)

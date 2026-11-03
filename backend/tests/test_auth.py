import datetime as dt

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.main import app
from app.models import RefreshToken, User
from tests.conftest import CSRF, PASSWORD, auth, register


def test_register_creates_customer_and_hashes_password(client, db):
    data = register(client, "New@Example.com", "Nina New")
    assert data["user"]["role"] == "customer"
    assert data["user"]["email"] == "new@example.com"  # lowercased
    assert "password" not in str(data).lower().replace("password_", "")
    user = db.scalar(select(User))
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash


def test_register_duplicate_email(client):
    register(client, "dup@example.com")
    r = client.post("/auth/register", json={"email": "DUP@example.com", "password": PASSWORD, "full_name": "X"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"


def test_register_rejects_weak_password_and_does_not_echo_it(client):
    r = client.post("/auth/register", json={"email": "a@example.com", "password": "short", "full_name": "A"})
    assert r.status_code == 422
    assert "short" not in r.text.replace("too short", "").replace("at least", "")  # value not echoed
    r = client.post("/auth/register", json={"email": "a@example.com", "password": "onlyletterslong", "full_name": "A"})
    assert r.status_code == 422


def test_register_cannot_choose_role(client):
    r = client.post("/auth/register", json={"email": "evil@example.com", "password": PASSWORD,
                                            "full_name": "Evil", "role": "staff"})
    assert r.status_code == 422


def test_login_ok_and_failures_look_identical(client):
    register(client, "me@example.com")
    ok = client.post("/auth/login", json={"email": "me@example.com", "password": PASSWORD})
    assert ok.status_code == 200 and ok.json()["access_token"]
    bad_pw = client.post("/auth/login", json={"email": "me@example.com", "password": "wrong-password-1"})
    no_user = client.post("/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert bad_pw.status_code == no_user.status_code == 401
    assert bad_pw.json() == no_user.json()  # can't tell which emails exist


def test_login_sets_secure_style_refresh_cookie(client):
    register(client, "c@example.com")
    r = client.post("/auth/login", json={"email": "c@example.com", "password": PASSWORD})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/auth" in cookie
    assert "refresh_token" not in r.text  # never in the JSON body


def test_protected_routes_need_a_valid_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=auth("garbage")).status_code == 401
    token = register(client, "t@example.com")["access_token"]
    assert client.get("/auth/me", headers=auth(token)).json()["email"] == "t@example.com"
    # Tampered signature
    assert client.get("/auth/me", headers=auth(token[:-3] + "abc")).status_code == 401


def test_expired_and_unsigned_tokens_rejected(client, db):
    s = get_settings()
    uid = register(client, "e@example.com")["user"]["id"]
    now = dt.datetime.now(dt.timezone.utc)
    expired = jwt.encode({"sub": uid, "typ": "access", "iat": now - dt.timedelta(hours=2),
                          "exp": now - dt.timedelta(hours=1)}, s.jwt_secret, algorithm="HS256")
    assert client.get("/auth/me", headers=auth(expired)).status_code == 401
    unsigned = jwt.encode({"sub": uid, "typ": "access", "iat": now, "exp": now + dt.timedelta(hours=1)},
                          None, algorithm="none")
    assert client.get("/auth/me", headers=auth(unsigned)).status_code == 401
    wrong_type = jwt.encode({"sub": uid, "typ": "refresh", "iat": now, "exp": now + dt.timedelta(hours=1)},
                            s.jwt_secret, algorithm="HS256")
    assert client.get("/auth/me", headers=auth(wrong_type)).status_code == 401


def test_refresh_rotates_and_detects_reuse(client, db):
    register(client, "r@example.com")  # cookie jar now holds refresh token #1
    old_cookie = client.cookies.get("refresh_token", path="/auth")
    r = client.post("/auth/refresh", headers=CSRF)
    assert r.status_code == 200 and r.json()["access_token"]
    new_cookie = client.cookies.get("refresh_token", path="/auth")
    assert new_cookie != old_cookie

    # Someone replays the OLD token: rejected, and every session of that user is revoked.
    attacker = TestClient(app)
    attacker.cookies.set("refresh_token", old_cookie, path="/auth")
    assert attacker.post("/auth/refresh", headers=CSRF).status_code == 401
    assert client.post("/auth/refresh", headers=CSRF).status_code == 401  # real user logged out too
    assert all(t.revoked_at is not None for t in db.scalars(select(RefreshToken)))


def test_refresh_and_logout_need_csrf_header_and_right_origin(client):
    register(client, "x@example.com")
    assert client.post("/auth/refresh").status_code == 403
    bad_origin = {**CSRF, "Origin": "https://evil.example"}
    assert client.post("/auth/refresh", headers=bad_origin).status_code == 403
    assert client.post("/auth/logout", headers=bad_origin).status_code == 403
    good_origin = {**CSRF, "Origin": get_settings().frontend_origin}
    assert client.post("/auth/refresh", headers=good_origin).status_code == 200


def test_logout_revokes_refresh_token(client):
    register(client, "l@example.com")
    stolen = client.cookies.get("refresh_token", path="/auth")
    assert client.post("/auth/logout", headers=CSRF).status_code == 204
    other = TestClient(app)
    other.cookies.set("refresh_token", stolen, path="/auth")
    assert other.post("/auth/refresh", headers=CSRF).status_code == 401


def test_profile_update(client):
    h = auth(register(client, "p@example.com")["access_token"])
    r = client.patch("/auth/me", json={"full_name": "  Pat Person ", "default_address": "5 Sample Road"}, headers=h)
    assert r.status_code == 200
    assert r.json()["full_name"] == "Pat Person" and r.json()["default_address"] == "5 Sample Road"
    assert client.patch("/auth/me", json={"role": "staff"}, headers=h).status_code == 422


def test_login_rate_limit_per_email(client, monkeypatch):
    """Guessing against ONE account is blocked after 8 tries (10 minutes window)."""
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    codes = [client.post("/auth/login", json={"email": "z@example.com", "password": "nope-nope-1"}).status_code
             for _ in range(10)]
    assert codes[:8] == [401] * 8
    assert codes[8:] == [429, 429]
    r = client.post("/auth/login", json={"email": "z@example.com", "password": "nope-nope-1"})
    assert "retry-after" in r.headers


def test_login_rate_limit_per_ip(client, monkeypatch):
    """Spraying many different emails from one IP is blocked after 10 tries per minute."""
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    codes = [client.post("/auth/login", json={"email": f"user{i}@example.com", "password": "nope-nope-1"}).status_code
             for i in range(12)]
    assert codes[:10] == [401] * 10
    assert codes[10:] == [429, 429]


def test_security_headers_and_cors(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    ok = client.options("/auth/login", headers={"Origin": get_settings().frontend_origin,
                                                "Access-Control-Request-Method": "POST"})
    assert ok.headers["access-control-allow-origin"] == get_settings().frontend_origin
    evil = client.options("/auth/login", headers={"Origin": "https://evil.example",
                                                  "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in evil.headers


def test_unexpected_errors_are_generic():
    @app.get("/_boom")
    def boom():
        raise RuntimeError("secret db password hunter2")

    r = TestClient(app, raise_server_exceptions=False).get("/_boom")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "server_error"
    assert "hunter2" not in r.text and "Traceback" not in r.text

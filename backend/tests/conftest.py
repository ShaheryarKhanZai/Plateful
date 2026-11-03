"""Test setup. Tests use a SEPARATE database (TEST_DATABASE_URL) that is wiped between
tests. A safety check refuses to run against any database whose name doesn't end in '_test'."""
import os
import pathlib
import re

import pytest


def _test_db_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    env_file = pathlib.Path(__file__).resolve().parent.parent / ".env"
    if not url and env_file.exists():
        m = re.search(r"^TEST_DATABASE_URL=(.+)$", env_file.read_text(), re.M)
        url = m.group(1).strip() if m else None
    if not url:
        pytest.exit("Set TEST_DATABASE_URL (see .env.example).", returncode=2)
    if not url.rsplit("/", 1)[-1].endswith("_test"):
        pytest.exit("TEST_DATABASE_URL must point to a database whose name ends in '_test'.", returncode=2)
    return url


# Must happen BEFORE the app is imported, so the app connects to the test database.
os.environ["DATABASE_URL"] = _test_db_url()
os.environ.setdefault("JWT_SECRET", "test-only-secret-that-is-long-enough-0123456789")
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["ENVIRONMENT"] = "development"

from decimal import Decimal  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402
from app.limiter import ALL_LIMITERS  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, MenuItem, Restaurant, RestaurantStaff, User  # noqa: E402
from app.security import hash_password  # noqa: E402

PASSWORD = "Correct-horse-9battery"
CSRF = {"X-Requested-With": "fetch"}


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def clean_db():
    with engine.begin() as conn:
        names = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    for limiter in ALL_LIMITERS:
        limiter.reset()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


# ---------- helpers ----------
def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient, email: str, name: str = "Test Person") -> dict:
    r = client.post("/auth/register", json={"email": email, "password": PASSWORD, "full_name": name})
    assert r.status_code == 201, r.text
    return r.json()


def customer_headers(client: TestClient, email: str = "cust@example.com") -> dict:
    return auth(register(client, email)["access_token"])


def make_restaurant(db, name="Test Kitchen", is_open=True) -> Restaurant:
    r = Restaurant(name=name, cuisine="Test", description="", is_open=is_open)
    db.add(r)
    db.commit()
    return r


def make_item(db, restaurant, name="Burger", price="8.50", available=True) -> MenuItem:
    m = MenuItem(restaurant_id=restaurant.id, name=name, description="", price=Decimal(price),
                 is_available=available)
    db.add(m)
    db.commit()
    return m


def staff_headers(client: TestClient, db, restaurants, email="staff@example.com") -> dict:
    u = User(email=email, full_name="Staff Person", role="staff", password_hash=hash_password(PASSWORD))
    db.add(u)
    db.flush()
    for r in restaurants:
        db.add(RestaurantStaff(user_id=u.id, restaurant_id=r.id))
    db.commit()
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return auth(r.json()["access_token"])


def place_order(client, headers, restaurant, lines, **overrides):
    body = {"restaurant_id": str(restaurant.id),
            "items": [{"menu_item_id": str(m.id), "quantity": q} for m, q in lines],
            "delivery_address": "12 Example Street", "payment_method": "mock_cash", **overrides}
    return client.post("/orders", json=body, headers=headers)

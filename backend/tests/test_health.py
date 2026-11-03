"""Health checks and the settings that make several API instances work side by side."""
from sqlalchemy.exc import OperationalError

import app.main as main_module
from app.config import get_settings
from app.database import engine
from app.models import Order


def test_liveness_is_ok(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_readiness_checks_the_database(client):
    r = client.get("/health/ready")
    assert r.status_code == 200 and r.json()["status"] == "ready"
    assert r.json()["instance"] == main_module.INSTANCE


def test_readiness_is_503_when_the_database_is_down_and_leaks_nothing(client, monkeypatch):
    class BrokenEngine:
        def connect(self):
            raise OperationalError("SELECT 1", None, Exception("password authentication failed for user x"))

    monkeypatch.setattr(main_module, "engine", BrokenEngine())
    r = client.get("/health/ready")
    assert r.status_code == 503
    assert r.json() == {"status": "unavailable"}   # no database details in the answer


def test_every_response_names_the_instance_that_served_it(client):
    for path in ("/health", "/restaurants", "/does-not-exist"):
        assert client.get(path).headers["x-instance"] == main_module.INSTANCE


def test_pool_size_comes_from_settings():
    s = get_settings()
    assert engine.pool.size() == s.db_pool_size
    assert engine.pool._max_overflow == s.db_max_overflow


def test_order_reads_server_generated_values_in_the_same_update():
    assert Order.__mapper__.eager_defaults is True

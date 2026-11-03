import pytest
from sqlalchemy import update

from app.models import Order
from app.services.orders import TRANSITIONS
from tests.conftest import customer_headers, make_item, make_restaurant, place_order, staff_headers

ALL = ["pending", "confirmed", "preparing", "out_for_delivery", "delivered", "cancelled"]


def _setup(client, db):
    r = make_restaurant(db)
    m = make_item(db, r)
    cust = customer_headers(client)
    order_id = place_order(client, cust, r, [(m, 1)]).json()["id"]
    return cust, staff_headers(client, db, [r]), order_id


def _force_status(db, order_id, status):
    db.execute(update(Order).where(Order.id == order_id).values(status=status))
    db.commit()


def test_happy_path_through_every_status(client, db):
    cust, staff, oid = _setup(client, db)
    for status in ["confirmed", "preparing", "out_for_delivery", "delivered"]:
        r = client.patch(f"/staff/orders/{oid}/status", json={"status": status}, headers=staff)
        assert r.status_code == 200 and r.json()["status"] == status
        assert client.get(f"/orders/{oid}", headers=cust).json()["status"] == status  # customer sees it


@pytest.mark.parametrize("current", ALL)
@pytest.mark.parametrize("target", ALL)
def test_staff_transition_matrix(client, db, current, target):
    _, staff, oid = _setup(client, db)
    _force_status(db, oid, current)
    r = client.patch(f"/staff/orders/{oid}/status", json={"status": target}, headers=staff)
    if target in TRANSITIONS[current]:
        assert r.status_code == 200 and r.json()["status"] == target
    else:
        assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_transition"
        db.expire_all()
        assert db.get(Order, oid).status == current  # unchanged


def test_transition_table_is_what_we_documented():
    assert TRANSITIONS == {
        "pending": {"confirmed", "cancelled"}, "confirmed": {"preparing", "cancelled"},
        "preparing": {"out_for_delivery"}, "out_for_delivery": {"delivered"},
        "delivered": set(), "cancelled": set()}


def test_unknown_status_value_rejected(client, db):
    _, staff, oid = _setup(client, db)
    for bad in ("shipped", "", "PENDING"):
        assert client.patch(f"/staff/orders/{oid}/status", json={"status": bad}, headers=staff).status_code == 422


def test_customer_can_cancel_only_while_pending(client, db):
    cust, _, oid = _setup(client, db)
    r = client.post(f"/orders/{oid}/cancel", headers=cust)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert client.post(f"/orders/{oid}/cancel", headers=cust).status_code == 409  # already cancelled

    other = make_restaurant(db, "Second")
    oid2 = place_order(client, cust, other, [(make_item(db, other), 1)]).json()["id"]
    _force_status(db, oid2, "confirmed")
    res = client.post(f"/orders/{oid2}/cancel", headers=cust)
    assert res.status_code == 409 and res.json()["error"]["code"] == "cannot_cancel"


def test_staff_filter_by_status(client, db):
    _, staff, _ = _setup(client, db)
    assert len(client.get("/staff/orders?status=pending", headers=staff).json()) == 1
    assert client.get("/staff/orders?status=delivered", headers=staff).json() == []
    assert client.get("/staff/orders?status=bogus", headers=staff).status_code == 422

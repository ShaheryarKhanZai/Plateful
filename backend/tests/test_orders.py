from decimal import Decimal

from sqlalchemy import func, select

from app.models import Order, OrderItem
from tests.conftest import customer_headers, make_item, make_restaurant, place_order, staff_headers


def test_total_is_calculated_from_database_prices(client, db):
    r = make_restaurant(db)
    burger, fries = make_item(db, r, "Burger", "8.50"), make_item(db, r, "Fries", "2.50")
    res = place_order(client, customer_headers(client), r, [(burger, 2), (fries, 1)])
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["total"] == "19.50" and body["status"] == "pending"
    assert {i["item_name"] for i in body["items"]} == {"Burger", "Fries"}


def test_money_math_is_exact(client, db):
    r = make_restaurant(db)
    dime = make_item(db, r, "Sticker", "0.10")
    res = place_order(client, customer_headers(client), r, [(dime, 3)])
    assert res.json()["total"] == "0.30"  # floats would give 0.30000000000000004


def test_browser_cannot_send_prices_or_totals(client, db):
    r = make_restaurant(db)
    m = make_item(db, r)
    h = customer_headers(client)
    for extra in ({"total": "0.01"}, {"status": "delivered"}, {"customer_id": "x"}):
        res = place_order(client, h, r, [(m, 1)], **extra)
        assert res.status_code == 422
    body = {"restaurant_id": str(r.id), "delivery_address": "12 Example Street", "payment_method": "mock_cash",
            "items": [{"menu_item_id": str(m.id), "quantity": 1, "price": "0.01"}]}
    assert client.post("/orders", json=body, headers=h).status_code == 422
    assert db.scalar(select(func.count()).select_from(Order)) == 0


def test_order_keeps_price_snapshot_after_menu_changes(client, db):
    r = make_restaurant(db)
    m = make_item(db, r, "Burger", "8.50")
    h = customer_headers(client)
    order_id = place_order(client, h, r, [(m, 1)]).json()["id"]
    m.price, m.name = Decimal("99.00"), "Renamed"
    db.commit()
    got = client.get(f"/orders/{order_id}", headers=h).json()
    assert got["total"] == "8.50"
    assert got["items"][0]["item_name"] == "Burger" and got["items"][0]["unit_price"] == "8.50"


def test_duplicate_lines_are_merged(client, db):
    r = make_restaurant(db)
    m = make_item(db, r)
    res = place_order(client, customer_headers(client), r, [(m, 2), (m, 3)])
    assert res.status_code == 201 and res.json()["items"][0]["quantity"] == 5
    assert place_order(client, customer_headers(client, "b@example.com"), r, [(m, 15), (m, 10)]).status_code == 422


def test_rejects_unavailable_item_and_creates_nothing(client, db):
    r = make_restaurant(db)
    ok, gone = make_item(db, r, "Burger"), make_item(db, r, "Kulfi", available=False)
    res = place_order(client, customer_headers(client), r, [(ok, 1), (gone, 1)])
    assert res.status_code == 409 and res.json()["error"]["code"] == "item_unavailable"
    assert "Kulfi" in res.json()["error"]["message"]
    assert db.scalar(select(func.count()).select_from(Order)) == 0
    assert db.scalar(select(func.count()).select_from(OrderItem)) == 0  # all-or-nothing


def test_rejects_closed_restaurant_and_unknown_restaurant(client, db):
    closed = make_restaurant(db, "Closed Place", is_open=False)
    m = make_item(db, closed)
    h = customer_headers(client)
    assert place_order(client, h, closed, [(m, 1)]).status_code == 409
    ghost = type("R", (), {"id": "00000000-0000-0000-0000-000000000000"})()
    assert place_order(client, h, ghost, [(m, 1)]).status_code == 404


def test_rejects_item_from_another_restaurant(client, db):
    a, b = make_restaurant(db, "A"), make_restaurant(db, "B")
    item_b = make_item(db, b)
    res = place_order(client, customer_headers(client), a, [(item_b, 1)])
    assert res.status_code == 422 and res.json()["error"]["code"] == "item_not_found"


def test_rejects_bad_quantities_and_empty_cart(client, db):
    r = make_restaurant(db)
    m = make_item(db, r)
    h = customer_headers(client)
    for q in (0, -1, 21):
        assert place_order(client, h, r, [(m, q)]).status_code == 422
    assert place_order(client, h, r, []).status_code == 422
    assert place_order(client, h, r, [(m, 1)], delivery_address="x").status_code == 422
    assert place_order(client, h, r, [(m, 1)], payment_method="visa").status_code == 422


def test_ordering_needs_a_customer_login(client, db):
    r = make_restaurant(db)
    m = make_item(db, r)
    assert place_order(client, {}, r, [(m, 1)]).status_code == 401
    assert place_order(client, staff_headers(client, db, [r]), r, [(m, 1)]).status_code == 403


def test_public_menu_endpoints(client, db):
    r = make_restaurant(db)
    make_item(db, r, "Burger")
    assert client.get("/restaurants").json()[0]["name"] == "Test Kitchen"
    menu = client.get(f"/restaurants/{r.id}/menu").json()
    assert menu["items"][0]["price"] == "8.50"
    assert client.get("/restaurants/not-a-uuid/menu").status_code == 422
    assert client.get("/restaurants/00000000-0000-0000-0000-000000000000/menu").status_code == 404

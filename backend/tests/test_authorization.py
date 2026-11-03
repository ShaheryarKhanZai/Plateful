"""Can a user reach something that isn't theirs by changing an ID?"""
from tests.conftest import customer_headers, make_item, make_restaurant, place_order, staff_headers


def _order(client, db, who="alice@example.com", restaurant=None):
    r = restaurant or make_restaurant(db)
    m = make_item(db, r)
    h = customer_headers(client, who)
    return h, r, place_order(client, h, r, [(m, 1)]).json()["id"]


def test_customer_cannot_read_or_cancel_someone_elses_order(client, db):
    _, _, alice_order = _order(client, db, "alice@example.com")
    bob = customer_headers(client, "bob@example.com")
    assert client.get(f"/orders/{alice_order}", headers=bob).status_code == 404
    assert client.post(f"/orders/{alice_order}/cancel", headers=bob).status_code == 404
    assert client.get("/orders", headers=bob).json() == []


def test_order_list_only_shows_own_orders(client, db):
    h, r, _ = _order(client, db, "alice@example.com")
    m = make_item(db, r, "Extra")
    place_order(client, h, r, [(m, 1)])
    assert len(client.get("/orders", headers=h).json()) == 2
    assert client.get("/orders", headers=customer_headers(client, "bob@example.com")).json() == []
    assert client.get("/orders").status_code == 401


def test_customer_cannot_use_staff_endpoints(client, db):
    h, _, order_id = _order(client, db)
    assert client.get("/staff/orders", headers=h).status_code == 403
    r = client.patch(f"/staff/orders/{order_id}/status", json={"status": "confirmed"}, headers=h)
    assert r.status_code == 403
    assert client.get("/staff/orders").status_code == 401


def test_staff_only_see_and_change_their_own_restaurants(client, db):
    mine, theirs = make_restaurant(db, "Mine"), make_restaurant(db, "Theirs")
    _, _, my_order = _order(client, db, "a@example.com", mine)
    _, _, other_order = _order(client, db, "b@example.com", theirs)
    staff = staff_headers(client, db, [mine])
    listed = client.get("/staff/orders", headers=staff).json()
    assert [o["id"] for o in listed] == [my_order]
    assert listed[0]["customer_name"]
    assert client.patch(f"/staff/orders/{other_order}/status", json={"status": "confirmed"},
                        headers=staff).status_code == 404
    assert client.patch(f"/staff/orders/{my_order}/status", json={"status": "confirmed"},
                        headers=staff).status_code == 200


def test_staff_without_restaurants_sees_nothing(client, db):
    _order(client, db)
    assert client.get("/staff/orders", headers=staff_headers(client, db, [])).json() == []


def test_customers_cannot_become_staff(client, db):
    h = customer_headers(client)
    me = client.get("/auth/me", headers=h).json()
    assert me["role"] == "customer"
    assert client.patch("/auth/me", json={"role": "staff"}, headers=h).status_code == 422

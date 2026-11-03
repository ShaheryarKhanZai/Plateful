"""Order business rules. Every important check happens here, on the server."""
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Order, OrderItem, User
from app.repositories import catalog, orders as repo
from app.schemas import OrderCreate

# Allowed status changes. Anything not listed here is rejected.
TRANSITIONS: dict[str, set[str]] = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"preparing", "cancelled"},
    "preparing": {"out_for_delivery"},
    "out_for_delivery": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}
MAX_QTY_PER_ITEM = 20


def _not_found() -> AppError:
    # Same answer whether the order doesn't exist or belongs to someone else,
    # so IDs can't be probed.
    return AppError(404, "order_not_found", "Order not found.")


def create_order(db: Session, customer: User, data: OrderCreate) -> Order:
    restaurant = catalog.get_restaurant(db, data.restaurant_id)
    if restaurant is None:
        raise AppError(404, "restaurant_not_found", "Restaurant not found.")
    if not restaurant.is_open:
        raise AppError(409, "restaurant_closed", f"{restaurant.name} is closed right now.")

    # Merge duplicate lines, then check the combined quantity.
    wanted: dict[uuid.UUID, int] = {}
    for line in data.items:
        wanted[line.menu_item_id] = wanted.get(line.menu_item_id, 0) + line.quantity
    if any(q > MAX_QTY_PER_ITEM for q in wanted.values()):
        raise AppError(422, "quantity_too_high", f"You can order at most {MAX_QTY_PER_ITEM} of one item.")

    # Prices and availability come from OUR database, never from the browser.
    menu = {m.id: m for m in catalog.get_menu_items(db, restaurant.id, list(wanted))}
    if len(menu) != len(wanted):
        raise AppError(422, "item_not_found", "An item in your cart is not on this restaurant's menu.")
    unavailable = sorted(m.name for m in menu.values() if not m.is_available)
    if unavailable:
        raise AppError(409, "item_unavailable", f"No longer available: {', '.join(unavailable)}.")

    order = Order(customer_id=customer.id, restaurant_id=restaurant.id, status="pending",
                  delivery_address=data.delivery_address, note=data.note or None,
                  payment_method=data.payment_method, total=Decimal("0.00"))
    total = Decimal("0.00")
    for item_id, qty in wanted.items():
        m = menu[item_id]
        total += m.price * qty
        # Snapshot name and price so later menu edits don't change this order.
        order.items.append(OrderItem(menu_item_id=m.id, item_name=m.name,
                                     unit_price=m.price, quantity=qty))
    order.total = total.quantize(Decimal("0.01"))

    # One transaction: the order and all its items are saved together, or not at all.
    try:
        db.add(order)
        db.commit()
    except Exception:
        db.rollback()
        raise
    created = repo.get(db, order.id)
    assert created is not None
    return created


def get_customer_order(db: Session, customer: User, order_id: uuid.UUID) -> Order:
    order = repo.get(db, order_id)
    if order is None or order.customer_id != customer.id:
        raise _not_found()
    return order


def cancel_own_order(db: Session, customer: User, order_id: uuid.UUID) -> Order:
    order = repo.get(db, order_id, for_update=True)
    if order is None or order.customer_id != customer.id:
        db.rollback()
        raise _not_found()
    if order.status != "pending":
        db.rollback()
        raise AppError(409, "cannot_cancel", "You can only cancel an order before the restaurant confirms it.")
    order.status = "cancelled"
    db.commit()
    return order


def staff_set_status(db: Session, staff: User, order_id: uuid.UUID, new_status: str) -> Order:
    order = repo.get(db, order_id, for_update=True)
    # Staff can only touch orders of restaurants they are linked to.
    if order is None or not repo.is_staff_of(db, staff.id, order.restaurant_id):
        db.rollback()
        raise _not_found()
    if new_status not in TRANSITIONS[order.status]:
        current = order.status
        db.rollback()
        raise AppError(409, "invalid_transition",
                       f"An order that is '{current}' can't be changed to '{new_status}'.")
    order.status = new_status
    db.commit()
    return order


def list_staff_orders(db: Session, staff: User, status: str | None, limit: int, offset: int) -> list[Order]:
    ids = repo.staff_restaurant_ids(db, staff.id)
    return repo.list_for_restaurants(db, ids, status, limit, offset) if ids else []

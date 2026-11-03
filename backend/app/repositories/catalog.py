import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MenuItem, Restaurant


def list_restaurants(db: Session) -> list[Restaurant]:
    return list(db.scalars(select(Restaurant).order_by(Restaurant.name)))


def get_restaurant(db: Session, restaurant_id: uuid.UUID) -> Restaurant | None:
    return db.get(Restaurant, restaurant_id)


def list_menu(db: Session, restaurant_id: uuid.UUID) -> list[MenuItem]:
    return list(db.scalars(
        select(MenuItem).where(MenuItem.restaurant_id == restaurant_id).order_by(MenuItem.name)))


def get_menu_items(db: Session, restaurant_id: uuid.UUID, ids: list[uuid.UUID]) -> list[MenuItem]:
    """Only items that belong to this restaurant. A foreign item ID simply won't be found."""
    return list(db.scalars(
        select(MenuItem).where(MenuItem.restaurant_id == restaurant_id, MenuItem.id.in_(ids))))

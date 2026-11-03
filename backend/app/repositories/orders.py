import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, RestaurantStaff


def get(db: Session, order_id: uuid.UUID, for_update: bool = False) -> Order | None:
    stmt = select(Order).where(Order.id == order_id)
    if for_update:
        # Locks just the order row so two requests can't change it at the same time.
        stmt = stmt.with_for_update(of=Order)
    return db.scalar(stmt)


def list_for_customer(db: Session, customer_id: uuid.UUID, limit: int, offset: int) -> list[Order]:
    stmt = (select(Order).where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc()).limit(limit).offset(offset))
    return list(db.scalars(stmt))


def staff_restaurant_ids(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(
        select(RestaurantStaff.restaurant_id).where(RestaurantStaff.user_id == user_id)))


def is_staff_of(db: Session, user_id: uuid.UUID, restaurant_id: uuid.UUID) -> bool:
    return db.get(RestaurantStaff, (user_id, restaurant_id)) is not None


def list_for_restaurants(db: Session, restaurant_ids: list[uuid.UUID], status: str | None,
                         limit: int, offset: int) -> list[Order]:
    stmt = select(Order).where(Order.restaurant_id.in_(restaurant_ids))
    if status:
        stmt = stmt.where(Order.status == status)
    return list(db.scalars(stmt.order_by(Order.created_at.desc()).limit(limit).offset(offset)))

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_customer
from app.models import User
from app.repositories import orders as repo
from app.schemas import OrderCreate, OrderOut
from app.services import orders as service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=201)
def place_order(body: OrderCreate, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    return service.create_order(db, user, body)


@router.get("", response_model=list[OrderOut])
def my_orders(limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0),
              user: User = Depends(require_customer), db: Session = Depends(get_db)):
    return repo.list_for_customer(db, user.id, limit, offset)


@router.get("/{order_id}", response_model=OrderOut)
def my_order(order_id: uuid.UUID, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    return service.get_customer_order(db, user, order_id)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel(order_id: uuid.UUID, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    return service.cancel_own_order(db, user, order_id)

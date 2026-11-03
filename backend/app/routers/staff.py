import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_staff
from app.models import User
from app.schemas import OrderStatus, StaffOrderOut, StatusUpdate
from app.services import orders as service

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/orders", response_model=list[StaffOrderOut])
def incoming_orders(status: OrderStatus | None = None, limit: int = Query(50, ge=1, le=100),
                    offset: int = Query(0, ge=0), user: User = Depends(require_staff),
                    db: Session = Depends(get_db)):
    return service.list_staff_orders(db, user, status, limit, offset)


@router.patch("/orders/{order_id}/status", response_model=StaffOrderOut)
def update_status(order_id: uuid.UUID, body: StatusUpdate, user: User = Depends(require_staff),
                  db: Session = Depends(get_db)):
    return service.staff_set_status(db, user, order_id, body.status)

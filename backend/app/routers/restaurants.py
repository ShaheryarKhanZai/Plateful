import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError
from app.repositories import catalog
from app.schemas import MenuOut, RestaurantOut

router = APIRouter(prefix="/restaurants", tags=["restaurants"])


@router.get("", response_model=list[RestaurantOut])
def list_restaurants(db: Session = Depends(get_db)):
    return catalog.list_restaurants(db)


@router.get("/{restaurant_id}/menu", response_model=MenuOut)
def get_menu(restaurant_id: uuid.UUID, db: Session = Depends(get_db)):
    restaurant = catalog.get_restaurant(db, restaurant_id)
    if restaurant is None:
        raise AppError(404, "restaurant_not_found", "Restaurant not found.")
    return MenuOut(restaurant=restaurant, items=catalog.list_menu(db, restaurant_id))  # type: ignore[arg-type]

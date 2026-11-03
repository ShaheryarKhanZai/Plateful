"""Request/response shapes. Pydantic rejects anything that doesn't fit."""
import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, computed_field, field_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=300)]
OrderStatus = Literal["pending", "confirmed", "preparing", "out_for_delivery", "delivered", "cancelled"]


class Strict(BaseModel):
    """Input models reject unknown fields, so a client can't sneak in e.g. a 'total'."""
    model_config = ConfigDict(extra="forbid")


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth / users ----
class RegisterIn(Strict):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: Name

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_has_letter_and_digit(cls, v: str) -> str:
        if not (any(c.isalpha() for c in v) and any(c.isdigit() for c in v)):
            raise ValueError("Password must contain at least one letter and one number")
        return v


class LoginIn(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower()


class ProfileUpdate(Strict):
    full_name: Name | None = None
    default_address: Address | None = None


class UserOut(Out):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    default_address: str | None


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---- catalog ----
class RestaurantOut(Out):
    id: uuid.UUID
    name: str
    description: str
    cuisine: str
    is_open: bool


class MenuItemOut(Out):
    id: uuid.UUID
    name: str
    description: str
    price: Decimal
    is_available: bool


class MenuOut(BaseModel):
    restaurant: RestaurantOut
    items: list[MenuItemOut]


# ---- orders ----
class OrderItemIn(Strict):
    menu_item_id: uuid.UUID
    quantity: int = Field(ge=1, le=20)


class OrderCreate(Strict):
    restaurant_id: uuid.UUID
    items: list[OrderItemIn] = Field(min_length=1, max_length=30)
    delivery_address: Address
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    # MOCK payment label only. We never collect card numbers.
    payment_method: Literal["mock_cash", "mock_card"]


class OrderItemOut(Out):
    item_name: str
    unit_price: Decimal
    quantity: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


class OrderOut(Out):
    id: uuid.UUID
    status: OrderStatus
    total: Decimal
    delivery_address: str
    note: str | None
    payment_method: str
    restaurant_id: uuid.UUID
    restaurant_name: str
    created_at: dt.datetime
    updated_at: dt.datetime
    items: list[OrderItemOut]


class StaffOrderOut(OrderOut):
    customer_name: str


class StatusUpdate(Strict):
    status: OrderStatus

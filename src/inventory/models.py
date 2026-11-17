"""Request and response bodies."""

from __future__ import annotations

from pydantic import BaseModel, Field

from inventory.store import Item

SKU_PATTERN = r"^[A-Za-z0-9-]{3,20}$"


class ItemCreate(BaseModel):
    sku: str = Field(pattern=SKU_PATTERN)
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(default="general", min_length=1, max_length=40)
    quantity: int = Field(default=0, ge=0)
    reorder_level: int = Field(default=0, ge=0)
    unit_price_pence: int = Field(ge=0)


class ItemUpdate(BaseModel):
    """Fields left out are not changed."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: str | None = Field(default=None, min_length=1, max_length=40)
    quantity: int | None = Field(default=None, ge=0)
    reorder_level: int | None = Field(default=None, ge=0)
    unit_price_pence: int | None = Field(default=None, ge=0)


class Adjustment(BaseModel):
    delta: int = Field(description="Units to add; negative to remove.")
    reason: str = Field(min_length=1, max_length=200)


class ItemOut(BaseModel):
    sku: str
    name: str
    category: str
    quantity: int
    reorder_level: int
    unit_price_pence: int
    low_stock: bool

    @classmethod
    def from_item(cls, item: Item) -> ItemOut:
        return cls(
            sku=item.sku,
            name=item.name,
            category=item.category,
            quantity=item.quantity,
            reorder_level=item.reorder_level,
            unit_price_pence=item.unit_price_pence,
            low_stock=item.low_stock,
        )

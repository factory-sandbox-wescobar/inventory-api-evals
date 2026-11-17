"""The in-memory stock store and its rules.

The store knows nothing about HTTP. It raises the errors below, and the app
turns them into status codes.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, replace


class NotFound(Exception):
    """No item has this SKU."""


class DuplicateSku(Exception):
    """An item with this SKU already exists."""


class InsufficientStock(Exception):
    """An adjustment would take the quantity below zero."""


@dataclass(frozen=True)
class Item:
    sku: str
    name: str
    category: str
    quantity: int
    reorder_level: int
    unit_price_pence: int

    @property
    def low_stock(self) -> bool:
        return self.quantity < self.reorder_level


class InventoryStore:
    """Items by SKU, safe to use from several request threads."""

    def __init__(self) -> None:
        self._items: dict[str, Item] = {}
        self._lock = threading.Lock()

    def list(self, category: str | None = None) -> list[Item]:
        with self._lock:
            items = list(self._items.values())
        if category is not None:
            items = [item for item in items if item.category == category]
        return sorted(items, key=lambda item: item.sku)

    def get(self, sku: str) -> Item:
        with self._lock:
            try:
                return self._items[sku]
            except KeyError:
                raise NotFound(sku) from None

    def create(self, item: Item) -> Item:
        with self._lock:
            if item.sku in self._items:
                raise DuplicateSku(item.sku)
            self._items[item.sku] = item
            return item

    def update(self, sku: str, **changes: object) -> Item:
        with self._lock:
            try:
                current = self._items[sku]
            except KeyError:
                raise NotFound(sku) from None
            updated = replace(current, **changes)
            self._items[sku] = updated
            return updated

    def delete(self, sku: str) -> None:
        with self._lock:
            try:
                del self._items[sku]
            except KeyError:
                raise NotFound(sku) from None

    def adjust(self, sku: str, delta: int) -> Item:
        """Add `delta` (negative to remove) to an item's quantity."""
        with self._lock:
            try:
                current = self._items[sku]
            except KeyError:
                raise NotFound(sku) from None
            new_quantity = current.quantity + delta
            if new_quantity < 0:
                raise InsufficientStock(sku)
            updated = replace(current, quantity=new_quantity)
            self._items[sku] = updated
            return updated

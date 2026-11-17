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


class VersionMismatch(Exception):
    """The item's current version is not the one the caller expected."""


@dataclass(frozen=True)
class Item:
    sku: str
    name: str
    category: str
    quantity: int
    reorder_level: int
    unit_price_pence: int
    version: int = 1

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
            item = replace(item, version=1)
            self._items[item.sku] = item
            return item

    def update(
        self, sku: str, *, expected_versions: frozenset[int] | None = None, **changes: object
    ) -> Item:
        """Change fields. If `expected_versions` is given, the item's current version
        must be in it, checked under the same lock as the change."""
        with self._lock:
            try:
                current = self._items[sku]
            except KeyError:
                raise NotFound(sku) from None
            self._check_version(current, expected_versions)
            updated = replace(current, **changes, version=current.version + 1)
            self._items[sku] = updated
            return updated

    def delete(self, sku: str) -> None:
        with self._lock:
            try:
                del self._items[sku]
            except KeyError:
                raise NotFound(sku) from None

    def adjust(
        self, sku: str, delta: int, *, expected_versions: frozenset[int] | None = None
    ) -> Item:
        """Add `delta` (negative to remove) to an item's quantity.

        If `expected_versions` is given, the item's current version must be in it,
        checked under the same lock as the change.
        """
        with self._lock:
            try:
                current = self._items[sku]
            except KeyError:
                raise NotFound(sku) from None
            self._check_version(current, expected_versions)
            new_quantity = current.quantity + delta
            if new_quantity < 0:
                raise InsufficientStock(sku)
            updated = replace(current, quantity=new_quantity, version=current.version + 1)
            self._items[sku] = updated
            return updated

    @staticmethod
    def _check_version(current: Item, expected_versions: frozenset[int] | None) -> None:
        if expected_versions is not None and current.version not in expected_versions:
            raise VersionMismatch(current.sku)

"""The interface every inventory store backend implements.

Backends raise `NotFound`, `DuplicateSku` and `InsufficientStock` (defined in
`inventory.store`) so the app can turn them into status codes whatever the
backend is.
"""

from __future__ import annotations

from typing import Protocol

from inventory.store import Item


class Store(Protocol):
    """Items by SKU."""

    def list(self, category: str | None = None) -> list[Item]:
        """All items (optionally one category), sorted by SKU."""
        ...

    def get(self, sku: str) -> Item:
        """Raise `NotFound` if there is no such item."""
        ...

    def create(self, item: Item) -> Item:
        """Raise `DuplicateSku` if the SKU already exists."""
        ...

    def update(self, sku: str, **changes: object) -> Item:
        """Raise `NotFound` if there is no such item."""
        ...

    def delete(self, sku: str) -> None:
        """Raise `NotFound` if there is no such item."""
        ...

    def adjust(self, sku: str, delta: int) -> Item:
        """Add `delta` (negative to remove) to an item's quantity.

        Raise `NotFound` if there is no such item, and `InsufficientStock` if
        the quantity would go below zero.
        """
        ...

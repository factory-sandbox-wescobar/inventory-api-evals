"""The interface every inventory store backend implements.

Backends raise `NotFound`, `DuplicateSku` and `InsufficientStock` (defined in
`inventory.store`) and return `Item` values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from inventory.store import Item


class Store(Protocol):
    """Items by SKU."""

    def list(self, category: str | None = None) -> list[Item]:
        """All items (optionally one category), sorted by SKU."""
        ...

    def get(self, sku: str) -> Item:
        """The item with this SKU. Raises `NotFound`."""
        ...

    def create(self, item: Item) -> Item:
        """Add an item. Raises `DuplicateSku`."""
        ...

    def update(self, sku: str, **changes: object) -> Item:
        """Change fields of an item. Raises `NotFound`."""
        ...

    def delete(self, sku: str) -> None:
        """Remove an item. Raises `NotFound`."""
        ...

    def adjust(self, sku: str, delta: int) -> Item:
        """Add `delta` (negative to remove) to an item's quantity.

        Raises `NotFound`, or `InsufficientStock` if the quantity would go below zero.
        """
        ...

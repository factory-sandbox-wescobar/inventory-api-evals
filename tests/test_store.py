from __future__ import annotations

import pytest

from inventory.store import DuplicateSku, InsufficientStock, InventoryStore, Item, NotFound


def make_item(sku: str = "WID-001", quantity: int = 10, reorder_level: int = 0) -> Item:
    return Item(
        sku=sku,
        name="Widget",
        category="parts",
        quantity=quantity,
        reorder_level=reorder_level,
        unit_price_pence=100,
    )


def test_create_then_get() -> None:
    store = InventoryStore()
    store.create(make_item())

    assert store.get("WID-001") == make_item()


def test_create_refuses_a_duplicate_sku() -> None:
    store = InventoryStore()
    store.create(make_item())

    with pytest.raises(DuplicateSku):
        store.create(make_item())


def test_adjust_refuses_to_go_below_zero() -> None:
    store = InventoryStore()
    store.create(make_item(quantity=2))

    with pytest.raises(InsufficientStock):
        store.adjust("WID-001", -3)
    assert store.get("WID-001").quantity == 2


def test_missing_items_raise_not_found() -> None:
    store = InventoryStore()

    for call in (
        lambda: store.get("NOPE"),
        lambda: store.update("NOPE", name="x"),
        lambda: store.delete("NOPE"),
        lambda: store.adjust("NOPE", 1),
    ):
        with pytest.raises(NotFound):
            call()


@pytest.mark.parametrize(
    ("quantity", "reorder_level", "expected"),
    [
        (2, 3, True),  # below the reorder level
        (3, 3, True),  # at the reorder level
        (4, 3, False),  # above the reorder level
        (0, 3, True),
        (0, 0, False),  # defaults: no reorder level, never low
        (5, 0, False),
    ],
)
def test_low_stock(quantity: int, reorder_level: int, expected: bool) -> None:
    item = make_item(quantity=quantity, reorder_level=reorder_level)

    assert item.low_stock is expected

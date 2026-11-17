from __future__ import annotations

from collections.abc import Callable

import pytest

from inventory.store import DuplicateSku, InsufficientStock, InventoryStore, Item, NotFound
from inventory.store_protocol import Store

# Add a factory here for each new backend; every store test then runs against it.
STORE_FACTORIES: list[Callable[[], Store]] = [InventoryStore]


@pytest.fixture(params=STORE_FACTORIES, ids=lambda factory: factory.__name__)
def store(request: pytest.FixtureRequest) -> Store:
    return request.param()


def make_item(sku: str = "WID-001", quantity: int = 10) -> Item:
    return Item(
        sku=sku,
        name="Widget",
        category="parts",
        quantity=quantity,
        reorder_level=0,
        unit_price_pence=100,
    )


def test_create_then_get(store: Store) -> None:
    store.create(make_item())

    assert store.get("WID-001") == make_item()


def test_create_refuses_a_duplicate_sku(store: Store) -> None:
    store.create(make_item())

    with pytest.raises(DuplicateSku):
        store.create(make_item())


def test_adjust_refuses_to_go_below_zero(store: Store) -> None:
    store.create(make_item(quantity=2))

    with pytest.raises(InsufficientStock):
        store.adjust("WID-001", -3)
    assert store.get("WID-001").quantity == 2


def test_missing_items_raise_not_found(store: Store) -> None:
    for call in (
        lambda: store.get("NOPE"),
        lambda: store.update("NOPE", name="x"),
        lambda: store.delete("NOPE"),
        lambda: store.adjust("NOPE", 1),
    ):
        with pytest.raises(NotFound):
            call()

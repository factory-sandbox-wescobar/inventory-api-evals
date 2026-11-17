from __future__ import annotations

import pytest

from inventory.store import DuplicateSku, InsufficientStock, InventoryStore, Item, NotFound


def make_item(sku: str = "WID-001", quantity: int = 10) -> Item:
    return Item(
        sku=sku,
        name="Widget",
        category="parts",
        quantity=quantity,
        reorder_level=0,
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


def test_create_stores_the_sku_upper_cased() -> None:
    store = InventoryStore()

    created = store.create(make_item(sku="ab-100"))

    assert created.sku == "AB-100"
    assert store.get("AB-100").sku == "AB-100"


def test_create_refuses_a_duplicate_sku_in_another_case() -> None:
    store = InventoryStore()
    store.create(make_item(sku="AB-100"))

    with pytest.raises(DuplicateSku):
        store.create(make_item(sku="ab-100"))


def test_lookups_ignore_the_case_of_the_sku() -> None:
    store = InventoryStore()
    store.create(make_item(sku="AB-100", quantity=5))

    assert store.get("ab-100").sku == "AB-100"
    assert store.update("ab-100", name="Renamed").name == "Renamed"
    assert store.adjust("Ab-100", 2).quantity == 7
    store.delete("aB-100")
    with pytest.raises(NotFound):
        store.get("AB-100")


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

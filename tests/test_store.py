from __future__ import annotations

import threading

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
        lambda: store.adjust_many([("NOPE", 1)]),
    ):
        with pytest.raises(NotFound):
            call()


def test_adjust_many_applies_every_adjustment() -> None:
    store = InventoryStore()
    store.create(make_item("WID-001", 10))
    store.create(make_item("BOLT-10", 0))

    items = store.adjust_many([("WID-001", -2), ("BOLT-10", 50)])

    assert [(i.sku, i.quantity) for i in items] == [("WID-001", 8), ("BOLT-10", 50)]
    assert store.get("WID-001").quantity == 8
    assert store.get("BOLT-10").quantity == 50


def test_adjust_many_uses_the_running_total_for_repeated_skus() -> None:
    store = InventoryStore()
    store.create(make_item(quantity=5))

    items = store.adjust_many([("WID-001", -5), ("WID-001", 3), ("WID-001", -3)])

    assert [(i.sku, i.quantity) for i in items] == [("WID-001", 0)]
    with pytest.raises(InsufficientStock):
        store.adjust_many([("WID-001", 4), ("WID-001", -5)])
    assert store.get("WID-001").quantity == 0


def test_adjust_many_changes_nothing_when_one_would_go_below_zero() -> None:
    store = InventoryStore()
    store.create(make_item("WID-001", 10))
    store.create(make_item("BOLT-10", 1))

    with pytest.raises(InsufficientStock) as raised:
        store.adjust_many([("WID-001", -2), ("BOLT-10", -2)])

    assert raised.value.args[0] == "BOLT-10"
    assert store.get("WID-001").quantity == 10
    assert store.get("BOLT-10").quantity == 1


def test_adjust_many_unknown_sku_wins_over_insufficient_stock() -> None:
    store = InventoryStore()
    store.create(make_item("WID-001", 1))

    with pytest.raises(NotFound) as raised:
        store.adjust_many([("WID-001", -5), ("NOPE-404", 1)])

    assert raised.value.args[0] == "NOPE-404"
    assert store.get("WID-001").quantity == 1


def test_adjust_many_with_nothing_returns_nothing() -> None:
    assert InventoryStore().adjust_many([]) == []


def test_concurrent_batches_never_take_stock_below_zero() -> None:
    store = InventoryStore()
    store.create(make_item(quantity=50))
    outcomes: list[bool] = []

    def worker() -> None:
        try:
            store.adjust_many([("WID-001", -3), ("WID-001", -2)])
            outcomes.append(True)
        except InsufficientStock:
            outcomes.append(False)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert outcomes.count(True) == 10
    assert store.get("WID-001").quantity == 0

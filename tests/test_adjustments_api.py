from __future__ import annotations

import threading

from fastapi.testclient import TestClient

from inventory.store import InventoryStore, Item
from tests.support import AUTH


def add_bolt(client: TestClient, quantity: int = 5) -> None:
    response = client.post(
        "/items",
        json={"sku": "BOLT-10", "name": "Bolt", "quantity": quantity, "unit_price_pence": 5},
        headers=AUTH,
    )
    assert response.status_code == 201


def quantity(client: TestClient, sku: str) -> int:
    return client.get(f"/items/{sku}").json()["quantity"]


def test_batch_applies_every_adjustment_and_returns_items(
    client: TestClient, widget: dict
) -> None:
    add_bolt(client)
    batch = [
        {"sku": "WID-001", "delta": -2, "reason": "order 1182"},
        {"sku": "BOLT-10", "delta": 50, "reason": "delivery"},
    ]

    response = client.post("/adjustments", json=batch, headers=AUTH)

    assert response.status_code == 200
    assert [(i["sku"], i["quantity"]) for i in response.json()] == [
        ("WID-001", 8),
        ("BOLT-10", 55),
    ]
    assert quantity(client, "WID-001") == 8
    assert quantity(client, "BOLT-10") == 55


def test_empty_batch_returns_an_empty_list(client: TestClient) -> None:
    response = client.post("/adjustments", json=[], headers=AUTH)

    assert response.status_code == 200
    assert response.json() == []


def test_unknown_sku_is_404_naming_it_and_changes_nothing(
    client: TestClient, widget: dict
) -> None:
    batch = [
        {"sku": "WID-001", "delta": -2, "reason": "order"},
        {"sku": "NOPE-404", "delta": 1, "reason": "delivery"},
    ]

    response = client.post("/adjustments", json=batch, headers=AUTH)

    assert response.status_code == 404
    assert "NOPE-404" in response.json()["detail"]
    assert quantity(client, "WID-001") == 10


def test_insufficient_stock_is_409_naming_it_and_changes_nothing(
    client: TestClient, widget: dict
) -> None:
    add_bolt(client, quantity=1)
    batch = [
        {"sku": "WID-001", "delta": -2, "reason": "order"},
        {"sku": "BOLT-10", "delta": -2, "reason": "order"},
    ]

    response = client.post("/adjustments", json=batch, headers=AUTH)

    assert response.status_code == 409
    assert "BOLT-10" in response.json()["detail"]
    assert quantity(client, "WID-001") == 10
    assert quantity(client, "BOLT-10") == 1


def test_unknown_sku_wins_over_insufficient_stock(client: TestClient, widget: dict) -> None:
    batch = [
        {"sku": "WID-001", "delta": -11, "reason": "order"},
        {"sku": "NOPE-404", "delta": 1, "reason": "delivery"},
    ]

    response = client.post("/adjustments", json=batch, headers=AUTH)

    assert response.status_code == 404
    assert quantity(client, "WID-001") == 10


def test_repeated_sku_uses_the_running_total(client: TestClient, widget: dict) -> None:
    ok = [
        {"sku": "WID-001", "delta": -8, "reason": "order"},
        {"sku": "WID-001", "delta": 5, "reason": "delivery"},
        {"sku": "WID-001", "delta": -7, "reason": "order"},
    ]
    response = client.post("/adjustments", json=ok, headers=AUTH)
    assert response.status_code == 200
    assert [i["quantity"] for i in response.json()] == [0]

    too_much = [
        {"sku": "WID-001", "delta": 3, "reason": "delivery"},
        {"sku": "WID-001", "delta": -2, "reason": "order"},
        {"sku": "WID-001", "delta": -2, "reason": "order"},
    ]
    response = client.post("/adjustments", json=too_much, headers=AUTH)
    assert response.status_code == 409
    assert quantity(client, "WID-001") == 0


def test_a_later_delivery_does_not_rescue_an_earlier_shortfall(
    client: TestClient, widget: dict
) -> None:
    batch = [
        {"sku": "WID-001", "delta": -11, "reason": "order"},
        {"sku": "WID-001", "delta": 20, "reason": "delivery"},
    ]

    response = client.post("/adjustments", json=batch, headers=AUTH)

    assert response.status_code == 409
    assert quantity(client, "WID-001") == 10


def test_batch_needs_the_api_key(client: TestClient, widget: dict) -> None:
    batch = [{"sku": "WID-001", "delta": -2, "reason": "order"}]

    assert client.post("/adjustments", json=batch).status_code == 401
    assert quantity(client, "WID-001") == 10


def test_batch_entries_are_validated(client: TestClient, widget: dict) -> None:
    response = client.post("/adjustments", json=[{"sku": "WID-001", "delta": 1}], headers=AUTH)

    assert response.status_code == 422


def test_concurrent_batches_never_take_stock_below_zero() -> None:
    store = InventoryStore()
    store.create(
        Item(
            sku="WID-001",
            name="Widget",
            category="parts",
            quantity=10,
            reorder_level=0,
            unit_price_pence=1,
        )
    )
    results: list[bool] = []

    def worker() -> None:
        try:
            store.adjust_many([("WID-001", -1), ("WID-001", -1)])
            results.append(True)
        except Exception:
            results.append(False)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count(True) == 5
    assert store.get("WID-001").quantity == 0

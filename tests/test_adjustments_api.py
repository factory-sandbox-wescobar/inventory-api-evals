from __future__ import annotations

from fastapi.testclient import TestClient

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


def test_batch_applies_every_adjustment_and_returns_the_items(
    client: TestClient, widget: dict
) -> None:
    add_bolt(client)

    response = client.post(
        "/adjustments",
        json=[
            {"sku": "WID-001", "delta": -2, "reason": "order 1182"},
            {"sku": "BOLT-10", "delta": 50, "reason": "delivery"},
        ],
        headers=AUTH,
    )

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


def test_unknown_sku_is_not_found_and_nothing_changes(client: TestClient, widget: dict) -> None:
    response = client.post(
        "/adjustments",
        json=[
            {"sku": "WID-001", "delta": -2, "reason": "order"},
            {"sku": "NOPE-404", "delta": 1, "reason": "delivery"},
        ],
        headers=AUTH,
    )

    assert response.status_code == 404
    assert "NOPE-404" in response.json()["detail"]
    assert quantity(client, "WID-001") == 10


def test_insufficient_stock_is_a_conflict_and_nothing_changes(
    client: TestClient, widget: dict
) -> None:
    add_bolt(client)

    response = client.post(
        "/adjustments",
        json=[
            {"sku": "BOLT-10", "delta": 10, "reason": "delivery"},
            {"sku": "WID-001", "delta": -11, "reason": "order"},
        ],
        headers=AUTH,
    )

    assert response.status_code == 409
    assert "WID-001" in response.json()["detail"]
    assert quantity(client, "WID-001") == 10
    assert quantity(client, "BOLT-10") == 5


def test_unknown_sku_wins_over_insufficient_stock(client: TestClient, widget: dict) -> None:
    response = client.post(
        "/adjustments",
        json=[
            {"sku": "WID-001", "delta": -11, "reason": "order"},
            {"sku": "NOPE-404", "delta": 1, "reason": "delivery"},
        ],
        headers=AUTH,
    )

    assert response.status_code == 404
    assert "NOPE-404" in response.json()["detail"]


def test_repeated_sku_uses_the_running_total(client: TestClient, widget: dict) -> None:
    ok = client.post(
        "/adjustments",
        json=[
            {"sku": "WID-001", "delta": -6, "reason": "order a"},
            {"sku": "WID-001", "delta": -4, "reason": "order b"},
        ],
        headers=AUTH,
    )
    assert ok.status_code == 200
    assert [(i["sku"], i["quantity"]) for i in ok.json()] == [("WID-001", 0)]
    assert quantity(client, "WID-001") == 0


def test_repeated_sku_going_below_zero_in_total_is_refused(
    client: TestClient, widget: dict
) -> None:
    response = client.post(
        "/adjustments",
        json=[
            {"sku": "WID-001", "delta": -6, "reason": "order a"},
            {"sku": "WID-001", "delta": -6, "reason": "order b"},
        ],
        headers=AUTH,
    )

    assert response.status_code == 409
    assert quantity(client, "WID-001") == 10


def test_batch_needs_the_api_key(client: TestClient, widget: dict) -> None:
    body = [{"sku": "WID-001", "delta": -1, "reason": "order"}]

    assert client.post("/adjustments", json=body).status_code == 401
    assert quantity(client, "WID-001") == 10


def test_batch_entries_need_a_reason(client: TestClient, widget: dict) -> None:
    response = client.post("/adjustments", json=[{"sku": "WID-001", "delta": 1}], headers=AUTH)

    assert response.status_code == 422

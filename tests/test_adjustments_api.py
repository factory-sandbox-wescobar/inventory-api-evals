from __future__ import annotations

from fastapi.testclient import TestClient

from tests.support import AUTH


def add_bolt(client: TestClient, quantity: int = 0) -> None:
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
        ("BOLT-10", 50),
    ]
    assert quantity(client, "WID-001") == 8
    assert quantity(client, "BOLT-10") == 50


def test_empty_batch_is_fine(client: TestClient) -> None:
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
    add_bolt(client, quantity=1)

    response = client.post(
        "/adjustments",
        json=[
            {"sku": "WID-001", "delta": -2, "reason": "order"},
            {"sku": "BOLT-10", "delta": -2, "reason": "order"},
        ],
        headers=AUTH,
    )

    assert response.status_code == 409
    assert "BOLT-10" in response.json()["detail"]
    assert quantity(client, "WID-001") == 10
    assert quantity(client, "BOLT-10") == 1


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
    assert quantity(client, "WID-001") == 10


def test_repeated_sku_uses_the_running_total(client: TestClient, widget: dict) -> None:
    ok = client.post(
        "/adjustments",
        json=[
            {"sku": "WID-001", "delta": -10, "reason": "order"},
            {"sku": "WID-001", "delta": 4, "reason": "return"},
        ],
        headers=AUTH,
    )
    assert ok.status_code == 200
    assert quantity(client, "WID-001") == 4

    refused = client.post(
        "/adjustments",
        json=[
            {"sku": "WID-001", "delta": -3, "reason": "order"},
            {"sku": "WID-001", "delta": -3, "reason": "order"},
        ],
        headers=AUTH,
    )
    assert refused.status_code == 409
    assert quantity(client, "WID-001") == 4


def test_batch_needs_the_api_key(client: TestClient, widget: dict) -> None:
    body = [{"sku": "WID-001", "delta": -1, "reason": "order"}]

    assert client.post("/adjustments", json=body).status_code == 401
    assert client.post("/adjustments", json=body, headers={"X-API-Key": "wrong"}).status_code == 401
    assert quantity(client, "WID-001") == 10


def test_batch_entries_need_a_sku_and_a_reason(client: TestClient, widget: dict) -> None:
    no_reason = client.post("/adjustments", json=[{"sku": "WID-001", "delta": 1}], headers=AUTH)
    no_sku = client.post("/adjustments", json=[{"delta": 1, "reason": "x"}], headers=AUTH)

    assert no_reason.status_code == 422
    assert no_sku.status_code == 422

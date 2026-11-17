from __future__ import annotations

from fastapi.testclient import TestClient

from tests.support import AUTH


def create(client: TestClient, sku: str) -> object:
    return client.post(
        "/items",
        json={"sku": sku, "name": "Thing", "quantity": 5, "unit_price_pence": 1},
        headers=AUTH,
    )


def test_create_stores_and_returns_the_sku_upper_cased(client: TestClient) -> None:
    response = create(client, "ab-100")

    assert response.status_code == 201
    assert response.json()["sku"] == "AB-100"
    assert [item["sku"] for item in client.get("/items").json()] == ["AB-100"]


def test_create_in_another_case_of_an_existing_sku_is_a_conflict(client: TestClient) -> None:
    assert create(client, "AB-100").status_code == 201

    assert create(client, "ab-100").status_code == 409


def test_get_finds_the_item_in_any_case(client: TestClient) -> None:
    create(client, "AB-100")

    response = client.get("/items/ab-100")

    assert response.status_code == 200
    assert response.json()["sku"] == "AB-100"


def test_update_finds_the_item_in_any_case(client: TestClient) -> None:
    create(client, "AB-100")

    response = client.patch("/items/ab-100", json={"name": "Renamed"}, headers=AUTH)

    assert response.status_code == 200
    assert response.json()["sku"] == "AB-100"
    assert response.json()["name"] == "Renamed"


def test_adjust_finds_the_item_in_any_case(client: TestClient) -> None:
    create(client, "AB-100")

    response = client.post(
        "/items/ab-100/adjust", json={"delta": 2, "reason": "delivery"}, headers=AUTH
    )

    assert response.status_code == 200
    assert response.json()["sku"] == "AB-100"
    assert response.json()["quantity"] == 7


def test_delete_finds_the_item_in_any_case(client: TestClient) -> None:
    create(client, "AB-100")

    assert client.delete("/items/ab-100", headers=AUTH).status_code == 204
    assert client.get("/items/AB-100").status_code == 404

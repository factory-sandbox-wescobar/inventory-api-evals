from __future__ import annotations

from fastapi.testclient import TestClient

from tests.support import AUTH


def test_create_item_returns_it_with_defaults(client: TestClient) -> None:
    response = client.post(
        "/items", json={"sku": "BOLT-10", "name": "Bolt", "unit_price_pence": 5}, headers=AUTH
    )

    assert response.status_code == 201
    assert response.json() == {
        "sku": "BOLT-10",
        "name": "Bolt",
        "category": "general",
        "quantity": 0,
        "reorder_level": 0,
        "unit_price_pence": 5,
        "low_stock": False,
        "version": 1,
    }


def test_create_duplicate_sku_is_a_conflict(client: TestClient, widget: dict) -> None:
    response = client.post(
        "/items", json={"sku": "WID-001", "name": "Other", "unit_price_pence": 1}, headers=AUTH
    )

    assert response.status_code == 409


def test_create_rejects_a_malformed_sku(client: TestClient) -> None:
    response = client.post(
        "/items", json={"sku": "no spaces!", "name": "Bad", "unit_price_pence": 1}, headers=AUTH
    )

    assert response.status_code == 422


def test_create_rejects_negative_quantity_and_price(client: TestClient) -> None:
    for field in ("quantity", "unit_price_pence"):
        body = {"sku": "NEG-001", "name": "Negative", "unit_price_pence": 1, field: -1}
        response = client.post("/items", json=body, headers=AUTH)
        assert response.status_code == 422, field


def test_get_item(client: TestClient, widget: dict) -> None:
    response = client.get("/items/WID-001")

    assert response.status_code == 200
    assert response.json() == widget


def test_get_item_returns_its_version_as_an_etag(client: TestClient, widget: dict) -> None:
    assert client.get("/items/WID-001").headers["ETag"] == '"1"'

    client.patch("/items/WID-001", json={"name": "Blue widget"}, headers=AUTH)

    assert client.get("/items/WID-001").headers["ETag"] == '"2"'


def test_get_unknown_item_is_not_found(client: TestClient) -> None:
    assert client.get("/items/NOPE-404").status_code == 404


def test_list_is_sorted_by_sku_and_filters_by_category(client: TestClient) -> None:
    for sku, category in [("C-300", "tools"), ("A-100", "parts"), ("B-200", "tools")]:
        client.post(
            "/items",
            json={"sku": sku, "name": sku, "category": category, "unit_price_pence": 1},
            headers=AUTH,
        )

    all_skus = [item["sku"] for item in client.get("/items").json()]
    tool_skus = [item["sku"] for item in client.get("/items?category=tools").json()]

    assert all_skus == ["A-100", "B-200", "C-300"]
    assert tool_skus == ["B-200", "C-300"]


def test_update_changes_only_the_fields_given(client: TestClient, widget: dict) -> None:
    response = client.patch(
        "/items/WID-001", json={"name": "Blue widget", "unit_price_pence": 300}, headers=AUTH
    )

    assert response.status_code == 200
    assert response.json() == {
        **widget,
        "name": "Blue widget",
        "unit_price_pence": 300,
        "version": 2,
    }


def test_update_unknown_item_is_not_found(client: TestClient) -> None:
    response = client.patch("/items/NOPE-404", json={"name": "x"}, headers=AUTH)

    assert response.status_code == 404


def test_update_with_matching_if_match_succeeds(client: TestClient, widget: dict) -> None:
    response = client.patch(
        "/items/WID-001", json={"name": "Blue"}, headers={**AUTH, "If-Match": '"1"'}
    )

    assert response.status_code == 200
    assert response.json()["version"] == 2


def test_update_with_stale_if_match_is_refused_and_changes_nothing(
    client: TestClient, widget: dict
) -> None:
    client.patch("/items/WID-001", json={"name": "First"}, headers=AUTH)

    response = client.patch(
        "/items/WID-001", json={"name": "Second"}, headers={**AUTH, "If-Match": '"1"'}
    )

    assert response.status_code == 412
    item = client.get("/items/WID-001").json()
    assert item["name"] == "First"
    assert item["version"] == 2


def test_update_with_garbage_if_match_is_refused(client: TestClient, widget: dict) -> None:
    response = client.patch(
        "/items/WID-001", json={"name": "x"}, headers={**AUTH, "If-Match": "banana"}
    )

    assert response.status_code == 412
    assert client.get("/items/WID-001").json()["version"] == 1


def test_delete_removes_the_item(client: TestClient, widget: dict) -> None:
    assert client.delete("/items/WID-001", headers=AUTH).status_code == 204
    assert client.get("/items/WID-001").status_code == 404
    assert client.delete("/items/WID-001", headers=AUTH).status_code == 404


def test_adjust_adds_and_removes_stock(client: TestClient, widget: dict) -> None:
    added = client.post("/items/WID-001/adjust", json={"delta": 5, "reason": "delivery"}, headers=AUTH)
    removed = client.post("/items/WID-001/adjust", json={"delta": -12, "reason": "order"}, headers=AUTH)

    assert added.json()["quantity"] == 15
    assert removed.json()["quantity"] == 3
    assert removed.json()["version"] == 3


def test_adjust_with_matching_if_match_succeeds(client: TestClient, widget: dict) -> None:
    response = client.post(
        "/items/WID-001/adjust",
        json={"delta": 1, "reason": "delivery"},
        headers={**AUTH, "If-Match": '"1"'},
    )

    assert response.status_code == 200
    assert response.json()["version"] == 2


def test_adjust_with_stale_if_match_is_refused_and_changes_nothing(
    client: TestClient, widget: dict
) -> None:
    client.post("/items/WID-001/adjust", json={"delta": 1, "reason": "delivery"}, headers=AUTH)

    response = client.post(
        "/items/WID-001/adjust",
        json={"delta": 5, "reason": "delivery"},
        headers={**AUTH, "If-Match": '"1"'},
    )

    assert response.status_code == 412
    item = client.get("/items/WID-001").json()
    assert item["quantity"] == 11
    assert item["version"] == 2


def test_adjust_below_zero_is_refused_and_changes_nothing(
    client: TestClient, widget: dict
) -> None:
    response = client.post(
        "/items/WID-001/adjust", json={"delta": -11, "reason": "order"}, headers=AUTH
    )

    assert response.status_code == 409
    item = client.get("/items/WID-001").json()
    assert item["quantity"] == 10
    assert item["version"] == 1


def test_adjust_needs_a_reason(client: TestClient, widget: dict) -> None:
    response = client.post("/items/WID-001/adjust", json={"delta": 1}, headers=AUTH)

    assert response.status_code == 422


def test_low_stock_when_quantity_is_under_the_reorder_level(
    client: TestClient, widget: dict
) -> None:
    client.post("/items/WID-001/adjust", json={"delta": -9, "reason": "order"}, headers=AUTH)

    item = client.get("/items/WID-001").json()

    assert item["quantity"] == 1
    assert item["low_stock"] is True

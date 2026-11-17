from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from inventory.app import create_app

NEW_ITEM = {"sku": "AUTH-01", "name": "Guarded", "unit_price_pence": 1}


def test_writes_need_the_api_key(client: TestClient) -> None:
    assert client.post("/items", json=NEW_ITEM).status_code == 401
    assert client.post("/items", json=NEW_ITEM, headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/items/AUTH-01").status_code == 404


def test_reads_need_no_key(client: TestClient) -> None:
    assert client.get("/items").status_code == 200


def test_with_no_key_configured_every_write_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INVENTORY_API_KEY", raising=False)
    client = TestClient(create_app())

    assert client.post("/items", json=NEW_ITEM, headers={"X-API-Key": ""}).status_code == 401


def test_key_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVENTORY_API_KEY", "from-env")
    client = TestClient(create_app())

    response = client.post("/items", json=NEW_ITEM, headers={"X-API-Key": "from-env"})

    assert response.status_code == 201

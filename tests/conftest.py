from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from inventory.app import create_app
from tests.support import API_KEY, AUTH


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(api_key=API_KEY))


@pytest.fixture
def widget(client: TestClient) -> dict:
    """One item already in stock."""
    response = client.post(
        "/items",
        json={
            "sku": "WID-001",
            "name": "Widget",
            "category": "parts",
            "quantity": 10,
            "reorder_level": 3,
            "unit_price_pence": 250,
        },
        headers=AUTH,
    )
    assert response.status_code == 201
    return response.json()

"""The HTTP API."""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Response, status

from inventory.auth import api_key_checker, configured_key
from inventory.models import Adjustment, ItemCreate, ItemOut, ItemUpdate
from inventory.protocol import Store
from inventory.store import DuplicateSku, InsufficientStock, InventoryStore, Item, NotFound


def create_app(api_key: str | None = None, store: Store | None = None) -> FastAPI:
    """Build the app. `api_key` defaults to the INVENTORY_API_KEY environment variable.

    `store` is any backend that implements the `Store` protocol; it defaults to
    a new in-memory store.
    """
    store = store if store is not None else InventoryStore()
    require_key = Depends(api_key_checker(api_key if api_key is not None else configured_key()))
    app = FastAPI(title="Inventory API", version="0.1.0")

    def not_found(sku: str) -> HTTPException:
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=f"no item with SKU {sku}")

    @app.get("/items", response_model=list[ItemOut])
    def list_items(category: str | None = None) -> list[ItemOut]:
        return [ItemOut.from_item(item) for item in store.list(category=category)]

    @app.post(
        "/items",
        response_model=ItemOut,
        status_code=status.HTTP_201_CREATED,
        dependencies=[require_key],
    )
    def create_item(body: ItemCreate) -> ItemOut:
        try:
            item = store.create(Item(**body.model_dump()))
        except DuplicateSku:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail=f"SKU {body.sku} already exists"
            ) from None
        return ItemOut.from_item(item)

    @app.get("/items/{sku}", response_model=ItemOut)
    def get_item(sku: str) -> ItemOut:
        try:
            return ItemOut.from_item(store.get(sku))
        except NotFound:
            raise not_found(sku) from None

    @app.patch("/items/{sku}", response_model=ItemOut, dependencies=[require_key])
    def update_item(sku: str, body: ItemUpdate) -> ItemOut:
        changes = body.model_dump(exclude_none=True)
        try:
            return ItemOut.from_item(store.update(sku, **changes))
        except NotFound:
            raise not_found(sku) from None

    @app.delete(
        "/items/{sku}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[require_key]
    )
    def delete_item(sku: str) -> Response:
        try:
            store.delete(sku)
        except NotFound:
            raise not_found(sku) from None
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/items/{sku}/adjust", response_model=ItemOut, dependencies=[require_key])
    def adjust_item(sku: str, body: Adjustment) -> ItemOut:
        try:
            return ItemOut.from_item(store.adjust(sku, body.delta))
        except NotFound:
            raise not_found(sku) from None
        except InsufficientStock:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"not enough stock of {sku} to remove {-body.delta}",
            ) from None

    return app


app = create_app()

"""The HTTP API."""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status

from inventory.auth import api_key_checker, configured_key
from inventory.models import Adjustment, ItemCreate, ItemOut, ItemUpdate
from inventory.store import (
    DuplicateSku,
    InsufficientStock,
    InventoryStore,
    Item,
    NotFound,
    VersionMismatch,
)


def etag_for(item: Item) -> str:
    return f'"{item.version}"'


def expected_version(if_match: str | None) -> int | None:
    """The version named by an If-Match header, or None if there is no check to make.

    A value that is not a version we could have issued never matches (-1).
    """
    if if_match is None:
        return None
    value = if_match.strip()
    if value == "*":
        return None
    if value.startswith("W/"):
        value = value[2:]
    value = value.strip('"')
    try:
        return int(value) if value.isdigit() else -1
    except ValueError:
        return -1


def create_app(api_key: str | None = None, store: InventoryStore | None = None) -> FastAPI:
    """Build the app. `api_key` defaults to the INVENTORY_API_KEY environment variable."""
    store = store if store is not None else InventoryStore()
    require_key = Depends(api_key_checker(api_key if api_key is not None else configured_key()))
    app = FastAPI(title="Inventory API", version="0.1.0")

    def not_found(sku: str) -> HTTPException:
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=f"no item with SKU {sku}")

    def version_mismatch(sku: str) -> HTTPException:
        return HTTPException(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f"item {sku} has changed; If-Match does not match its current version",
        )

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
    def get_item(sku: str, response: Response) -> ItemOut:
        try:
            item = store.get(sku)
        except NotFound:
            raise not_found(sku) from None
        response.headers["ETag"] = etag_for(item)
        return ItemOut.from_item(item)

    @app.patch("/items/{sku}", response_model=ItemOut, dependencies=[require_key])
    def update_item(
        sku: str,
        body: ItemUpdate,
        response: Response,
        if_match: str | None = Header(default=None),
    ) -> ItemOut:
        changes = body.model_dump(exclude_none=True)
        try:
            item = store.update(sku, expected_version=expected_version(if_match), **changes)
        except NotFound:
            raise not_found(sku) from None
        except VersionMismatch:
            raise version_mismatch(sku) from None
        response.headers["ETag"] = etag_for(item)
        return ItemOut.from_item(item)

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
    def adjust_item(
        sku: str,
        body: Adjustment,
        response: Response,
        if_match: str | None = Header(default=None),
    ) -> ItemOut:
        try:
            item = store.adjust(sku, body.delta, expected_version=expected_version(if_match))
        except NotFound:
            raise not_found(sku) from None
        except VersionMismatch:
            raise version_mismatch(sku) from None
        except InsufficientStock:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"not enough stock of {sku} to remove {-body.delta}",
            ) from None
        response.headers["ETag"] = etag_for(item)
        return ItemOut.from_item(item)

    return app


app = create_app()

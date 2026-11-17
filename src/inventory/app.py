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


def etag(item: Item) -> str:
    return f'"{item.version}"'


def parse_if_match(value: str | None) -> frozenset[int] | None:
    """The versions an If-Match header accepts; None when the header is absent.

    Values that are not a version number (and so can never match) give an empty
    set. `*` matches any existing item, so it also gives None (no check).
    """
    if value is None:
        return None
    versions: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if part == "*":
            return None
        if part.startswith("W/"):
            part = part[2:]
        part = part.strip('"')
        if part.isascii() and part.isdigit():
            versions.add(int(part))
    return frozenset(versions)


def create_app(api_key: str | None = None, store: InventoryStore | None = None) -> FastAPI:
    """Build the app. `api_key` defaults to the INVENTORY_API_KEY environment variable."""
    store = store if store is not None else InventoryStore()
    require_key = Depends(api_key_checker(api_key if api_key is not None else configured_key()))
    app = FastAPI(title="Inventory API", version="0.1.0")

    def not_found(sku: str) -> HTTPException:
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=f"no item with SKU {sku}")

    def precondition_failed(sku: str) -> HTTPException:
        return HTTPException(
            status.HTTP_412_PRECONDITION_FAILED,
            detail=f"item {sku} has changed; its version does not match If-Match",
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
        response.headers["ETag"] = etag(item)
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
            item = store.update(sku, expected_versions=parse_if_match(if_match), **changes)
        except NotFound:
            raise not_found(sku) from None
        except VersionMismatch:
            raise precondition_failed(sku) from None
        response.headers["ETag"] = etag(item)
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
            item = store.adjust(sku, body.delta, expected_versions=parse_if_match(if_match))
        except NotFound:
            raise not_found(sku) from None
        except VersionMismatch:
            raise precondition_failed(sku) from None
        except InsufficientStock:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"not enough stock of {sku} to remove {-body.delta}",
            ) from None
        response.headers["ETag"] = etag(item)
        return ItemOut.from_item(item)

    return app


app = create_app()

# Inventory API

A small HTTP API that keeps track of stock: items, how many of each are on hand, and when to reorder. Stock lives in memory, so it is empty each time the service starts.

Built with FastAPI. Python 3.12.

## Rules

These are how the service is meant to behave. Where the code disagrees, the code is wrong.

- **SKU:** upper-case letters, digits and hyphens, 3 to 20 characters, for example `WID-001`. SKUs are unique regardless of case.
- **Name:** 1 to 100 characters, not counting leading or trailing spaces.
- **Category:** 1 to 40 characters. Defaults to `general`.
- **Quantity** and **reorder level** are whole numbers, never negative. Quantity defaults to 0.
- **Price** is `unit_price_pence`, a whole number of pence, never negative. Money is never a float.
- **Low stock:** an item is low on stock when its quantity is at or below its reorder level.
- **Adjustments** add to or remove from the quantity, with a reason. An adjustment that would take the quantity below zero is refused and changes nothing.
- **Batch adjustments** (`POST /adjustments`) apply all together or not at all. An unknown SKU anywhere in the batch is a 404 and beats any 409; otherwise a SKU whose running total would go below zero is a 409. The error names the SKU and nothing changes. The same SKU may appear more than once; checks use the running total in list order.
- **Writes** (create, update, delete, adjust) need the `X-API-Key` header to match the `INVENTORY_API_KEY` environment variable. Reads need no key. With no key set, every write is refused.

## Endpoints

| Method and path | Key | What it does | Responses |
|---|---|---|---|
| `GET /items?category=` | no | List items sorted by SKU, optionally in one category | 200 |
| `POST /items` | yes | Create an item | 201, 409 SKU exists, 422 invalid |
| `GET /items/{sku}` | no | One item | 200, 404 |
| `PATCH /items/{sku}` | yes | Change some of an item's fields | 200, 404, 422 |
| `DELETE /items/{sku}` | yes | Remove an item | 204, 404 |
| `POST /items/{sku}/adjust` | yes | Body `{"delta": -2, "reason": "order 1182"}` | 200, 404, 409 not enough stock, 422 |
| `POST /adjustments` | yes | Body is a list of `{"sku", "delta", "reason"}`; all or nothing. Returns the updated items, one per distinct SKU in order of first appearance (`[]` for an empty list) | 200, 404 unknown SKU, 409 not enough stock, 422 |

Every item in a response has `sku`, `name`, `category`, `quantity`, `reorder_level`, `unit_price_pence` and `low_stock`. Errors are FastAPI's usual `{"detail": ...}`. Interactive docs are at `/docs` while the service runs.

## Run it

With [uv](https://docs.astral.sh/uv/):

```bash
INVENTORY_API_KEY=dev-key uv run uvicorn inventory.app:app --reload
curl -s -X POST localhost:8000/items -H 'X-API-Key: dev-key' -H 'Content-Type: application/json' \
  -d '{"sku": "WID-001", "name": "Widget", "quantity": 10, "reorder_level": 3, "unit_price_pence": 250}'
curl -s localhost:8000/items
```

Or with a plain virtual environment:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[test]'
INVENTORY_API_KEY=dev-key .venv/bin/uvicorn inventory.app:app --reload
```

## Test it

```bash
uv run --extra test pytest
# or
.venv/bin/python -m pytest
```

CI runs the same tests on every pull request (`.github/workflows/ci.yml`, check name `tests`).

## Layout

| Path | Holds |
|---|---|
| `src/inventory/app.py` | The routes; turns store errors into status codes |
| `src/inventory/models.py` | Request and response bodies, and their validation |
| `src/inventory/store.py` | The in-memory store and the stock rules; knows nothing about HTTP |
| `src/inventory/auth.py` | The API key check |
| `tests/` | pytest suite, one file per module plus the API tests |

## Contributing

- Every change goes through a pull request to `main`; direct pushes are blocked.
- Add or change tests with the code. A pull request whose tests fail is not merged.
- Keep dependencies pinned to exact versions in `pyproject.toml`.
- Some paths are protected: `.factory/protected-paths.txt` lists them. A change to any of them needs a review from the code owners in `CODEOWNERS`, and will not merge on its own. That includes the list itself.
- Branches written by the software factory start with `factory/`, and its commits carry a `Factory-Run:` trailer.

"""API key check for the endpoints that change stock.

This is a protected path (see .factory/protected-paths.txt): any change to it
needs a maintainer's review.
"""

from __future__ import annotations

import hmac
import os
from collections.abc import Callable

from fastapi import Header, HTTPException, status

API_KEY_ENV = "INVENTORY_API_KEY"


def configured_key() -> str | None:
    """The key from the environment, or None when it is unset or empty."""
    return os.environ.get(API_KEY_ENV) or None


def api_key_checker(expected: str | None) -> Callable[[str | None], None]:
    """A FastAPI dependency that accepts only `expected` in `X-API-Key`.

    With no key configured every write is refused: the service fails closed.
    """

    def check(x_api_key: str | None = Header(default=None)) -> None:
        if expected is None or x_api_key is None or not hmac.compare_digest(
            x_api_key.encode(), expected.encode()
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="a valid X-API-Key header is required",
            )

    return check
